ASUS Ascent GX10 (NVIDIA GB10, 128 GB unified memory), DGX OS 7.5.
Runtimes: Ollama (nemotron35, qwen38, gptoss), llama.cpp llama-server (qwopus36, deepseek).
Models: NVIDIA-Nemotron-3.5-Lightning-30B-A3B IQ4_NL; Qwen3.8-27B Q4_K_M; gpt-oss-120b MXFP4;
Qwen3.6-35B-A3B Q6 with MTP draft (alias qwopus36); DeepSeek-V4-Flash UD-IQ2_XXS.
Five full runs 27.10.2026: results_20261027_1341 .. _1717.
results_20261027_1213: first full single run, max_tokens 16000.
results_20261027_1331: DeepSeek go_worker_pool rerun alone with max_tokens 32000 (passed, 251 s).
results_20261027_1341..1717: the five runs quoted in the write-up, max_tokens 32000.
