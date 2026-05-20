// ── Count refresh ──────────────────────────────────────────────────────────
async function refreshCount() {
    try {
        const response = await fetch("/count");
        const data = await response.json();
        document.getElementById("vehicleCount").textContent = data.count;
    } catch (_) {}
}

// ── Video loader ───────────────────────────────────────────────────────────
const videoFeed   = document.getElementById("videoFeed");
const videoLoader = document.getElementById("videoLoader");

videoFeed.addEventListener("load", () => {
    videoLoader.style.display = "none";
});

// Safety: if the image src never fires "load" (e.g. stream not yet started),
// keep the loader visible until frames actually arrive.
videoFeed.addEventListener("error", () => {
    videoLoader.style.display = "flex";
});

// ── Camera switch buttons ──────────────────────────────────────────────────
document.querySelectorAll("[data-stream]").forEach((button) => {
    button.addEventListener("click", async () => {
        const streamId = button.dataset.stream;

        // Show loading overlay while the new stream spins up
        videoLoader.style.display = "flex";

        // Swap out the img src so the browser re-requests /video_feed after
        // the backend has switched — avoids stale frames briefly showing.
        videoFeed.src = "";

        await fetch("/switch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stream_id: streamId }),
        });

        document.querySelectorAll("[data-stream]").forEach((item) =>
            item.classList.remove("active")
        );
        button.classList.add("active");
        document.getElementById("locationName").textContent =
            window.STREAM_NAMES[streamId];
        document.getElementById("vehicleCount").textContent = "0";

        // Reload the video feed after a short pause to let the backend catch up
        setTimeout(() => {
            videoFeed.src = "/video_feed";
        }, 800);
    });
});

// ── Stop program ───────────────────────────────────────────────────────────
document.getElementById("stopProgram").addEventListener("click", async () => {
    const stopButton = document.getElementById("stopProgram");
    stopButton.textContent = "Stopping...";
    stopButton.classList.add("stopping");
    document.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
        await fetch("/shutdown", { method: "POST" });
        document.getElementById("locationName").textContent = "Program stopped";
    } catch (_) {
        document.getElementById("locationName").textContent = "Program stopped";
    }
});

refreshCount();
setInterval(refreshCount, 500);

// ── Game Logic ─────────────────────────────────────────────────────────────
let gameActive = false;
const GAME_DURATION = 15; // seconds

/**
 * Poll /game_snapshot until the backend reports ready=true AND the
 * frame_seq matches the expectedSeq (the seq that was live when the
 * user clicked Start).  This prevents the timer firing on a stale
 * frame left over from a previous camera switch.
 *
 * Returns a promise that resolves with the snapshot data once live,
 * or rejects with a reason string after 90 seconds.
 */
function waitForFreshStream(expectedSeq, statusDiv) {
    return new Promise((resolve, reject) => {
        const startedAt  = Date.now();
        const MAX_WAIT   = 90_000;
        let   dotCount   = 0;

        const poll = async () => {
            if (Date.now() - startedAt > MAX_WAIT) {
                reject("timeout");
                return;
            }

            let data;
            try {
                const res = await fetch("/game_snapshot");
                data = await res.json();
            } catch (_) {
                reject("network");
                return;
            }

            // Ready only when: this stream's first frame has been processed
            // AND the seq is still the one we started with (no camera switch)
            if (data.ready && data.seq === expectedSeq) {
                resolve(data);
            } else {
                dotCount = (dotCount + 1) % 4;
                const dots = ".".repeat(dotCount);
                statusDiv.textContent = data.seq !== expectedSeq
                    ? `🔄 Stream switching${dots}`
                    : `⏳ Waiting for camera${dots}`;
                setTimeout(poll, 800);
            }
        };
        poll();
    });
}

document.getElementById("startGameBtn").addEventListener("click", async () => {
    if (gameActive) return;

    const guessInput = document.getElementById("guessInput");
    const statusDiv  = document.getElementById("gameStatus");
    const progressBar = document.getElementById("gameProgress");
    const guessValue = parseInt(guessInput.value, 10);

    // ── Validate input ────────────────────────────────────────────────────────
    if (isNaN(guessValue) || guessValue < 0) {
        statusDiv.textContent = "⚠️ Please enter a valid number (0 or more).";
        statusDiv.className   = "game-status lose-text";
        return;
    }

    gameActive = true;
    guessInput.disabled = true;
    document.getElementById("startGameBtn").disabled = true;

    // ── Phase 1: Read current seq BEFORE waiting so we can detect switches ───
    let initData;
    try {
        const res = await fetch("/game_snapshot");
        initData  = await res.json();
    } catch (_) {
        statusDiv.textContent = "❌ Could not connect to server. Try again.";
        statusDiv.className   = "game-status lose-text";
        resetGame();
        return;
    }

    const expectedSeq = initData.seq;

    // ── Phase 2: Wait until the stream is genuinely live ─────────────────────
    statusDiv.className   = "game-status";
    statusDiv.textContent = "⏳ Waiting for camera…";
    if (progressBar) { progressBar.style.width = "0%"; progressBar.style.opacity = "1"; }

    let startData;
    try {
        startData = await waitForFreshStream(expectedSeq, statusDiv);
    } catch (reason) {
        const msg = reason === "timeout"
            ? "❌ Stream took too long to start. Try switching cameras."
            : "❌ Could not connect to server. Try again.";
        statusDiv.textContent = msg;
        statusDiv.className   = "game-status lose-text";
        resetGame();
        return;
    }

    const startCount  = startData.count;
    const startStream = startData.stream;

    // ── Phase 3: 15-second countdown ─────────────────────────────────────────
    // Show "15s" IMMEDIATELY so the user sees the full count before the first
    // tick fires (the common bug where it jumps straight to "14s").
    let timeLeft = GAME_DURATION;
    statusDiv.className   = "game-status";
    statusDiv.textContent = `⏱ ${timeLeft}s — count the cars crossing the line!`;
    if (progressBar) progressBar.style.width = "100%";

    const timer = setInterval(async () => {
        timeLeft -= 1;

        // Update countdown bar
        const pct = Math.max(0, (timeLeft / GAME_DURATION) * 100);
        if (progressBar) progressBar.style.width = `${pct}%`;

        if (timeLeft > 0) {
            statusDiv.textContent = `⏱ ${timeLeft}s — count the cars crossing the line!`;
            return;
        }

        // ── Time is up ───────────────────────────────────────────────────────
        clearInterval(timer);
        if (progressBar) { progressBar.style.width = "0%"; progressBar.style.opacity = "0"; }

        let finalData;
        try {
            const res = await fetch("/game_snapshot");
            finalData = await res.json();
        } catch (_) {
            statusDiv.textContent = "❌ Lost connection at the end. Try again.";
            statusDiv.className   = "game-status lose-text";
            resetGame();
            return;
        }

        // Camera switched mid-game → result is invalid
        if (finalData.stream !== startStream || finalData.seq !== expectedSeq) {
            statusDiv.textContent = "🔄 Camera switched mid-game — result cancelled. Play again!";
            statusDiv.className   = "game-status";
            resetGame();
            return;
        }

        const carsPassed = finalData.count - startCount;
        const diff       = Math.abs(carsPassed - guessValue);

        if (diff === 0) {
            statusDiv.textContent = `🏆 PERFECT! Exactly ${carsPassed} car${carsPassed !== 1 ? "s" : ""} passed!`;
            statusDiv.className   = "game-status win-text";
        } else if (diff === 1) {
            statusDiv.textContent = `🎉 So Close! ${carsPassed} car${carsPassed !== 1 ? "s" : ""} passed — off by just 1!`;
            statusDiv.className   = "game-status win-text";
        } else if (diff <= 3) {
            statusDiv.textContent = `👍 Almost! ${carsPassed} car${carsPassed !== 1 ? "s" : ""} passed — you guessed ${guessValue}.`;
            statusDiv.className   = "game-status win-text";
        } else {
            statusDiv.textContent = `😔 Not quite! You guessed ${guessValue}, but ${carsPassed} car${carsPassed !== 1 ? "s" : ""} passed.`;
            statusDiv.className   = "game-status lose-text";
        }

        resetGame();
    }, 1000);
});

function resetGame() {
    gameActive = false;
    document.getElementById("guessInput").disabled   = false;
    document.getElementById("startGameBtn").disabled = false;
}

