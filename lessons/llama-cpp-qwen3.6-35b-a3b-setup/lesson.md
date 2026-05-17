# Running llama.cpp locally with Qwen3.6 35B A3B and systemd

There is a moment in every local-LLM journey where the toy `ollama run` command is no longer enough. You want a real OpenAI-compatible endpoint sitting on a stable port. You want it to come back after a reboot. You want to pick the model, pick the quantisation, pick the context window, and pick how the experts of a mixture-of-experts model are laid out across CPU and GPU. That is the job `llama.cpp` was built for, and the version of `llama-server` shipping in 2026 has finally caught up to a point where running a 35-billion-parameter MoE on a single workstation is genuinely practical.

This lesson is the end-to-end recipe. We will build `llama.cpp` from source with CUDA support, download Unsloth's GGUF conversion of **Qwen3.6 35B A3B**, work through the runtime flags that actually matter for an MoE this size, and wrap the whole thing in a systemd unit that starts on boot, restarts on failure, and logs to the journal. By the end you will have a local `/v1/chat/completions` endpoint that behaves like a tiny private OpenAI account.

The target audience is someone comfortable with the Linux command line who has either an NVIDIA GPU with 12–24 GB of VRAM or a recent workstation CPU with enough system RAM to host the routed experts. The exact split is tunable, which is most of what makes this interesting.

## The model in one paragraph

**Qwen3.6 35B A3B** is a mixture-of-experts model from Alibaba's Qwen team. The number "35B" is the total parameter count; "A3B" — *active 3B* — is the number of parameters actually doing work per token. The architecture has 256 experts per MoE layer, of which 8 are routed plus 1 shared expert per forward pass. The practical consequence is that memory cost scales with 35B but compute scales closer to a 3B dense model, which is why these models punch far above their compute weight on consumer hardware. Native context is 262,144 tokens, extensible further with YaRN. Unsloth's GGUF builds publish quantisations from `UD-IQ1_M` (around 10 GB) up to `BF16` (around 70 GB); for a 24 GB VRAM card the `UD-Q4_K_M` build at roughly 22 GB is the usual sweet spot, and even an 8–12 GB card is reachable if you route the routed-expert FFN weights to CPU.

## Step 1: build llama.cpp from source

You can install `llama.cpp` from Homebrew, winget, Docker images, or the pre-built release tarballs on GitHub. For a Linux server we will build from source: it is the only way to get a binary tuned to your specific CUDA setup, and the project moves fast enough that a checkout from `master` is often weeks ahead of any package.

Prerequisites on a Debian or Ubuntu host:

```bash
sudo apt update
sudo apt install -y git cmake build-essential libcurl4-openssl-dev ccache
# For NVIDIA GPU acceleration, install the CUDA toolkit from NVIDIA's apt repo.
# The package name is cuda-toolkit-12-x or similar; verify nvcc --version works.
```

Clone the repository and build with CUDA enabled:

```bash
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=ON
cmake --build build --config Release -j --clean-first \
  --target llama-server llama-cli llama-gguf-split
```

A few notes on the flags. `-DGGML_CUDA=ON` is what compiles the CUDA kernels. `-DLLAMA_CURL=ON` is what lets `llama-server` resolve `-hf user/repo:quant` shortcuts directly from Hugging Face — without it you are stuck pre-downloading every GGUF by hand. The explicit `--target` list keeps the build narrow; without it you compile every example, which doubles the compile time for binaries you will never touch.

If you do not have a GPU, drop `-DGGML_CUDA=ON`. The CPU build is the same in every other respect; runtime performance on a 35B A3B model will be in the 2–5 tokens-per-second range on a recent workstation, which is fine for chat-shaped workloads but slow for batch jobs.

When the build finishes, the binaries live under `build/bin/`. Put that directory on your `PATH`, or symlink the two binaries you actually use into `/usr/local/bin`:

```bash
sudo ln -s "$PWD/build/bin/llama-server" /usr/local/bin/llama-server
sudo ln -s "$PWD/build/bin/llama-cli" /usr/local/bin/llama-cli
```

Verify with `llama-server --version`.

## Step 2: get the GGUF weights

The model lives at <https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF>. There are three reasonable ways to pull it down.

**Option A — let `llama-server` do it.** If you built with `LLAMA_CURL=ON`, you can pass `-hf` and the server will resolve the file on first run, cache it under `~/.cache/llama.cpp/`, and reuse it afterwards:

```bash
llama-server -hf unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_M
```

The colon-suffix is the quantisation tag, matching the file naming on the repo (e.g. `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`).

**Option B — `huggingface-cli`.** More explicit, easier to script, and gives you a known on-disk path:

```bash
pip install --upgrade "huggingface_hub[cli]"
huggingface-cli download unsloth/Qwen3.6-35B-A3B-GGUF \
  Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
  --local-dir /srv/models/qwen3.6-35b-a3b
```

You can swap in any quantisation tag from the repo. The Unsloth "Unsloth Dynamic 2.0" (`UD-*`) builds use a calibrated importance matrix to bump load-bearing tensors to higher precision than vanilla `Q4_K_M`, which materially helps MoE models at 3-bit and 4-bit.

**Option C — `wget`/`curl` the file directly** from the Hugging Face LFS URL. Fine for one-off runs; awkward to keep in sync with the repo's revisions.

Pick a quantisation that fits your hardware:

| Quantisation | Approx. size | Fits | Notes |
| --- | --- | --- | --- |
| `UD-IQ2_M` | 11.5 GB | 12 GB VRAM card | Acceptable quality for a 35B MoE at 2-bit |
| `UD-Q3_K_M` | 16.6 GB | 16 GB VRAM card | Good 3-bit balance |
| `UD-Q4_K_M` | 22.1 GB | 24 GB VRAM card | The default recommendation |
| `Q8_0` | 36.9 GB | dual GPU or partial CPU offload | Near-lossless quality |
| `BF16` | 69.4 GB | system RAM or CPU offload | Reference weights |

## Step 3: the runtime flags that matter

`llama-server` has dozens of flags. For a model like this, six of them are load-bearing and the rest are noise.

```bash
llama-server \
  -m /srv/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  --ctx-size 32768 \
  --n-gpu-layers 999 \
  --threads 8 \
  --threads-batch 16 \
  --batch-size 2048 \
  --ubatch-size 512 \
  --parallel 2 \
  --jinja \
  --api-key "$LLAMA_API_KEY"
```

The flags, in the order they actually affect what happens:

- **`-m, --model`** — path to the GGUF file. The single non-optional flag.
- **`--host` / `--port`** — bind address. Default is `127.0.0.1:8080`, which is what you want unless you are also putting a reverse proxy in front. Do not bind to `0.0.0.0` without an auth gate.
- **`-c, --ctx-size`** — context window in tokens, allocated up front in VRAM as a KV cache. `0` lets the model pick its native size (262K for this model), which will not fit in any sane GPU; pick a realistic working number. 32K is a good starting point. Doubling the context roughly doubles KV-cache memory.
- **`-ngl, --n-gpu-layers`** — number of transformer layers to offload to GPU. The conventional value is `999` (or `-1`) which means "all layers", and is correct when you want everything on the GPU. Combine with the MoE offload flags below if you need to claw back VRAM.
- **`-t, --threads` / `-tb, --threads-batch`** — CPU threads for generation and for batch processing. Set `threads` to your physical core count and `threads-batch` higher (e.g. logical core count) since batch-mode is more parallel-friendly. With full GPU offload this has marginal effect; with CPU experts it is everything.
- **`-b, --batch-size` / `-ub, --ubatch-size`** — logical and physical batch sizes for prompt processing. Larger batches improve prefill throughput at the cost of memory; defaults of 2048/512 are fine for most setups.
- **`-np, --parallel`** — number of concurrent request slots. `--ctx-size` is divided across slots, so `--ctx-size 32768 --parallel 2` gives each request a 16K window. Default is `-1` (auto).
- **`--jinja`** — use the model's embedded Jinja chat template, which is what gives you correct system/user/assistant turn formatting and tool-calling support. Leave it on for chat models; turn it off only if you have a strict reason.
- **`--api-key`** — require this token on every request. Without it your endpoint is wide open to anyone who can reach the port. With it, OpenAI clients pointed at your URL with this string as `OPENAI_API_KEY` will just work.

## Step 4: the MoE-specific flags

This is the part of the lesson that pays the rent. A naive `-ngl 999` says "put everything on the GPU", which for a 22 GB quantisation on a 24 GB card leaves no room for the KV cache. The trick for MoE models is that the routed-expert weights are touched only when their expert is selected for a given token — they are the largest tensors in the model and the least-frequently used. If you push them to CPU and keep attention plus the shared expert on GPU, you get most of the speed of a fully-resident model for a fraction of the VRAM.

Two flags do this.

**`-cmoe, --cpu-moe`** keeps *all* MoE weights on the CPU. Simplest possible knob. Use it when you have minimal VRAM and a fast CPU.

**`-ncmoe, --n-cpu-moe N`** keeps the MoE weights of the *first N layers* on CPU and lets the remaining layers' experts live on the GPU. This is the dial you turn to fill exactly the VRAM you have, no more and no less. There is no formula — you start at a low value, watch `nvidia-smi`, and creep upward until you are comfortably under the VRAM ceiling.

A 12 GB card with `UD-Q4_K_M` looks like this:

```bash
llama-server \
  -m /srv/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
  --ctx-size 16384 \
  --n-gpu-layers 999 \
  --n-cpu-moe 32 \
  --threads 12
```

For finer-grained control, `-ot, --override-tensor` accepts a regex matching tensor names. The canonical "push every routed-expert FFN to CPU" recipe is:

```bash
llama-server \
  -m /srv/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
  --ctx-size 32768 \
  --n-gpu-layers 999 \
  --override-tensor "exps=CPU"
```

That single `exps=CPU` regex catches all the expert FFN weights — the bulky, rarely-touched part — and leaves everything else, including attention and the shared expert, on the GPU. On a 24 GB card you can usually run a full 64K context this way.

A note on sampling defaults. Qwen3 publishes recommended sampler settings, and they matter more than people expect. For the thinking-mode general case: `--temp 1.0 --top-p 0.95 --top-k 20 --presence-penalty 1.5`. For instruct-style chat: `--temp 0.7 --top-p 0.8 --top-k 20`. The server will accept these as CLI flags or as per-request overrides in the chat-completions body.

## Step 5: verify the endpoint by hand

With the server running, the obvious smoke test is a `GET /v1/models`:

```bash
curl -s http://127.0.0.1:8080/v1/models \
  -H "Authorization: Bearer $LLAMA_API_KEY" | jq
```

You should see a single model object whose `id` matches the GGUF filename (or whatever you passed with `--alias`). If you get an empty list, the server is still loading; if you get a 401, your `--api-key` flag and `Authorization` header disagree.

Then a real chat completion:

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer $LLAMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.6-35b-a3b",
    "messages": [
      {"role": "system", "content": "You are a concise assistant."},
      {"role": "user", "content": "In one sentence, what is a mixture-of-experts model?"}
    ],
    "temperature": 0.7
  }' | jq
```

If that returns a sensible answer, your endpoint is live and OpenAI-shaped. Pointing the Python `openai` SDK at `http://127.0.0.1:8080/v1` with any non-empty API key works without further changes.

## Step 6: wrap it in a systemd service

Running `llama-server` in a terminal is fine to confirm the model works. For day-to-day use you want it managed by `systemd`: starts on boot, restarts on crash, logs to the journal, runs as a non-privileged user.

### Create a dedicated system user

```bash
sudo useradd --system --create-home --home /var/lib/llama \
  --shell /usr/sbin/nologin llama
sudo mkdir -p /srv/models /var/log/llama
sudo chown -R llama:llama /var/lib/llama /var/log/llama
sudo chown -R llama:llama /srv/models
```

If you have an NVIDIA GPU, the `llama` user needs to be able to talk to the device nodes under `/dev/nvidia*`. On most installs the default permissions on those nodes already allow this; if not, add the user to the `video` group.

### Drop an environment file

Putting parameters in a separate `EnvironmentFile` keeps the unit clean and makes tuning a one-line edit instead of a unit-file rewrite. Save this as `/etc/llama-server.env`:

```ini
LLAMA_MODEL=/srv/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
LLAMA_HOST=127.0.0.1
LLAMA_PORT=8080
LLAMA_CTX=32768
LLAMA_NGL=999
LLAMA_NCMOE=0
LLAMA_THREADS=8
LLAMA_API_KEY=replace-me-with-a-long-random-string
```

Lock it down: `sudo chmod 600 /etc/llama-server.env && sudo chown root:llama /etc/llama-server.env`.

### Write the unit file

Save this as `/etc/systemd/system/llama-server.service`:

```ini
[Unit]
Description=llama.cpp HTTP server (Qwen3.6 35B A3B)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=llama
Group=llama
EnvironmentFile=/etc/llama-server.env
ExecStart=/usr/local/bin/llama-server \
  --model ${LLAMA_MODEL} \
  --host ${LLAMA_HOST} \
  --port ${LLAMA_PORT} \
  --ctx-size ${LLAMA_CTX} \
  --n-gpu-layers ${LLAMA_NGL} \
  --n-cpu-moe ${LLAMA_NCMOE} \
  --threads ${LLAMA_THREADS} \
  --jinja \
  --api-key ${LLAMA_API_KEY}

Restart=on-failure
RestartSec=10
TimeoutStartSec=600

# Sandboxing
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/llama /var/log/llama
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
RestrictSUIDSGID=yes
LockPersonality=yes

# Resource limits
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

A few notes on what's doing work.

`After=network-online.target` matters more than you'd think: the `-hf` shortcut hits Hugging Face, and on first boot you need the network to actually be up rather than just configured. If you pre-downloaded the model, this is less critical, but it costs nothing.

`TimeoutStartSec=600` exists because loading a 22 GB GGUF into VRAM is not instant. Without an extended timeout, systemd will declare the unit failed before the model finishes loading, especially on a cold page cache. Ten minutes is generous; reduce once you know your actual startup time.

The sandboxing block is standard systemd hygiene. `NoNewPrivileges=yes` blocks `setuid` escalations from inside the service. `ProtectSystem=strict` makes the filesystem read-only except for explicitly listed `ReadWritePaths`. `ProtectHome=yes` hides every home directory other than the service user's. `PrivateTmp=yes` gives the service its own ephemeral `/tmp`. These are not security theatre — they meaningfully reduce blast radius if the service is ever compromised, and they cost nothing on a service that just reads model files and serves HTTP.

### Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now llama-server.service
```

The `--now` flag is a shorthand for "enable for boot and also start it right now." Check status with:

```bash
systemctl status llama-server.service
journalctl -fu llama-server.service
```

The first `journalctl` line should be `llama-server` printing its build info, followed by GGUF metadata, then layer-load progress. When you see `HTTP server listening, hostname: 127.0.0.1, port: 8080`, the endpoint is live.

To change the context size or VRAM layout, edit `/etc/llama-server.env` and `sudo systemctl restart llama-server.service`. The unit file itself rarely needs to change once it works.

## What we deliberately skipped

A few things are intentionally out of scope.

- **Reverse proxy and TLS.** If you are exposing this beyond localhost, put nginx or Caddy in front of port 8080 with a real certificate. Do not bind `llama-server` directly to a public address.
- **GPU drivers.** This lesson assumes a working CUDA stack. Installing the driver and matching toolkit is its own topic.
- **Multi-GPU layouts.** With two or more GPUs you can split layers across devices with `-ts, --tensor-split` and assign experts per-device with `--override-tensor`. The same principles apply, but the regex tuning gets fiddly.
- **Speculative decoding.** Recent llama.cpp supports a draft model speeding up the main one. Public benchmarks on Qwen3.6 35B A3B with an Ampere-class GPU suggest no net speedup on this specific MoE, so it is not worth the complexity here.
- **llama-swap and model rotation.** If you want to serve multiple models from the same port and swap them on demand, `llama-swap` sits in front of multiple `llama-server` instances and routes requests. Once you have one model running stably as a service, swapping it out is a small extension of the same systemd pattern.

What you have at this point is a reproducible, version-controlled local inference endpoint: identical API surface to OpenAI, predictable startup behaviour, sensible sandboxing, and a single environment file to tune. From here it is just a question of what you point at it.
