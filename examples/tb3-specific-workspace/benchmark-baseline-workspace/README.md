# benchmark-baseline workspace

A minimal psi-agent workspace designed as the **common baseline** across all four
benchmark evaluation lines: TB 2.1, TB 3.0, tau2, and GAIA.

## Design principle

The initial Skills/Tools Setup is **identical** for all four benchmarks. This ensures:

- No per-benchmark tool/skill configuration drift
- Baseline (HaiTun Base) and experimental (HaiTun Full) differ only in skills,
  not in core tools
- Cross-benchmark ablation comparisons are not confounded by tool differences

## Structure

- `tools/` — 13 universal tools:
  - `bash.py` — shell command execution (fresh `bash -lc` per call; 120s default timeout; output truncated)
  - `read.py` — file reading with offset/limit
  - `write.py` — file creation/overwrite
  - `edit.py` — precise string replacement
  - `search.py` — file finding (glob, supports `**`) + content search (regex)
  - `list_dir.py` — directory browsing (flat or recursive)
  - `background_start.py` — launch detached long-running processes (auto-captures stdout/stderr to a log file, returns `log_path`)
  - `background_stop.py` — terminate a background process by id (also defines `background_list`)
  - `fetch.py` — URL retrieval; main article extracted as Markdown (binary refused, output capped)
  - `read_pdf.py` — PDF text extraction (pdftotext / pymupdf / pdfplumber; `force_ocr=True` for scanned PDFs via tesseract)
  - `diff.py` — unified diff between a file and another file or inline expected content
  - `artifact_validate.py` — generic acceptance checklist (exists / non-empty / contains / not_contains / exact_match / regex / size)
- `skills/_universal/SKILL.md` — cross-benchmark working discipline (always-on)
- `systems/system.py` — minimal system prompt builder + context compaction

## What's deliberately excluded

- **Domain skills** (cryptanalysis, ml-inference, etc.) — TB2-specific, would
  contaminate other benchmarks
- **Web search tool** — GAIA needs it, but TB3 prohibits task-specific search;
  GAIA gets it from its adapter instead. `fetch` is included for reading
  general documentation, but `_universal` skill explicitly prohibits using it
  to search for task-specific solutions.
- **Benchmark-specific prompt sections** — no container-isolation mentions,
  no multi-turn-user instructions; those come from the benchmark adapter/framework

## How each benchmark uses this workspace

| Benchmark | Tools used from this workspace | Additional tools from adapter |
|-----------|-------------------------------|-------------------------------|
| TB 2.1 | bash, read, write, edit, search, list_dir, background_start/stop | none |
| TB 3.0 | bash, read, write, edit, search, list_dir, background_start/stop | none (verifier runs separately) |
| tau2 | (mostly unused — agent converses via adapter) | tau2 domain API tools |
| GAIA | bash, read, write, edit, search, list_dir, fetch, read_pdf | web_search (from GAIA adapter) |

## Why these tools

| Tool | Why it's universal | Driven by |
|------|-------------------|-----------|
| bash | Fresh per-call shell execution (cwd/env/venv do not persist; chain with `&&`) | All TB tasks |
| read | Read file contents | All benchmarks |
| write | Create files / artifacts | TB 2.1/3.0, GAIA |
| edit | Precise string replacement | TB 2.1/3.0 (code modification) |
| search | Glob file finding (supports `**`) + regex content search | TB 2.1/3.0 (codebase exploration), GAIA |
| list_dir | Browse directory tree | TB 2.1/3.0 (environment exploration), GAIA |
| background_start | Long-running ML/compile/proof tasks (auto-captures output to log file) | TB 2.1 (caffe-cifar-10, llm-inference), TB 3.0 (vllm, gpt2-codegolf, takens-embedding) |
| background_stop | Terminate stuck processes | Companion to background_start |
| background_list | Inspect which background processes are alive | Companion to background_start |
| fetch | Read web documentation / API refs as Markdown | GAIA (research), TB (general docs) |
| read_pdf | Extract text from PDF files (incl. OCR fallback for scanned PDFs) | GAIA (file/multimodal tasks), TB (PDF docs) |
| diff | Unified diff between a file and another file or expected content — inspect edits, compare deliverables | All benchmarks (verification) |
| artifact_validate | Run the task's stated acceptance criteria (exists/non-empty/contains/not_contains/exact_match/regex/size) against a file or directory | All benchmarks (verification) |

## 容器运行时假设（deployment checklist）

psi-agent 框架跑在 adapter 建的 **Python 3.14 venv** 里（pyproject 要求 `>=3.14`；
任务镜像自带的系统 python 3.12 不直接运行 psi-agent）。本 workspace 的工具只依赖
psi-agent 正式依赖 + Python 标准库，无需额外安装任何东西：

| 依赖 | 由谁提供 | 容器状态（TB3 镜像实测） |
|------|----------|--------------------------|
| anyio / aiohttp / loguru | psi-agent 依赖（venv 3.14） | ✅ |
| markdownify / readability（fetch） | psi-agent 依赖（venv 3.14） | ✅ + 出站网络 ✅ |
| pymupdf / fitz（read_pdf） | psi-agent 依赖（venv 3.14） | ✅ read_pdf 走 `sys.executable`（venv），不依赖系统 python3 |
| bash | 任务镜像自带 | ✅ |
| pdftotext / pdftoppm / tesseract（read_pdf OCR） | 需 apt 安装，容器无 | ⚠️ 缺失时 read_pdf 优雅降级（文本 PDF 由 pymupdf 覆盖） |
| diff / artifact_validate | 纯 stdlib（difflib/re）+ anyio | ✅ 零额外依赖 |

> 注意：不同 TB3 任务镜像环境可能不同（基础镜像、预装包不一致）。改动 workspace
> 或 adapter 后按下面 smoke 流程复验，不要假设环境不变。

## Adapter smoke（改动 workspace / adapter 后必跑）

`harbor run -a oracle` 走 Harbor 内置 OracleAgent，**完全不经过 PsiAgent adapter**，
所以 oracle 通过**不能证明 adapter 能跑**。每次改 workspace / adapter / 框架版本后，
用 1 个真实 agent case 验证全链路：

```bash
# 1. 部署 workspace 到宿主机，并让 .env 指向它
#    PSI_AGENT_REPO=<你的 psi-agent fork>
#    PSI_AGENT_REF=codex/tb3-baseline
#    PSI_AGENT_WORKSPACE=<宿主机上的 baseline workspace 路径>

# 2. 跑 1 个 case（真实 agent，不是 oracle）
cd $TB_BENCH_WORKDIR && . .env
python3 bin/run_all_cases.py --cases <case-name> --run-id smoke

# 3. 检查四件事
#    a. install 阶段：uv/git/venv 3.14/workspace 上传成功（无报错）
#    b. run 阶段：ai.sock / ch.sock 起来、CLI 跑完
#    c. 日志落盘：pilot_results/<case>/ai.log、session.log、agent_output.log 存在
#    d. 工具被实际调用：agent_output.log 里能看到期望的 tool_calls（如 diff / artifact_validate）
```

## Run


```bash
psi-agent ai --provider <name> --model <model> --api-key <key> --base-url <url> --session-socket /tmp/ai.sock
psi-agent session --workspace examples/benchmark-baseline-workspace --ai-socket /tmp/ai.sock --channel-socket /tmp/ch.sock
psi-agent channel repl --session-socket /tmp/ch.sock
```
