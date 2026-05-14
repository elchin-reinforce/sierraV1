# Free Models Guide

## Default (No API Key Required)

### Rule-based agent + Scripted user
Zero cost, zero network. Good for testing and baselines.

```bash
python -m taufreebench.cli run-episode --agent rule --user scripted --domain retail --task retail_task_001
```

### Ollama (local LLMs)

Install: https://ollama.ai

```bash
ollama serve
ollama pull qwen3:8b      # Best tool-calling performance
ollama pull llama3.1:8b   # Good general performance
ollama pull gemma3:4b     # Fast, lower memory
```

Run with Ollama:
```bash
python -m taufreebench.cli run-episode --agent ollama --agent-model qwen3:8b --user scripted
```

## Hosted Free Tiers (API Key Required)

### Gemini Flash (Google AI Studio)

Free tier: https://aistudio.google.com/app/apikey

```bash
export GEMINI_API_KEY="your-key"
python -m taufreebench.cli run-episode --agent gemini --domain retail --task retail_task_001
```

### Groq (Llama 3.1)

Free tier: https://console.groq.com/keys

```bash
export GROQ_API_KEY="your-key"
python -m taufreebench.cli run-episode --agent groq --domain retail --task retail_task_001
```

### OpenRouter (free models)

Free models: https://openrouter.ai/models?q=free

```bash
export OPENROUTER_API_KEY="your-key"
python -m taufreebench.cli run-episode --agent openrouter --domain retail --task retail_task_001
```

## Adding a New Provider

1. Create `providers/my_provider.py` inheriting from `ChatProvider`
2. Implement `is_available()` and `chat()`
3. Create `agents/my_tool_agent.py` using your provider
4. Add to `providers/model_registry.py`
5. Register in `providers/free_model_discovery.py`
6. Add agent factory in `runners/run_episode.py`

## Auto-Calibration

Run calibration to find the best available model automatically:

```bash
python -m taufreebench.cli calibrate-free-models --domain retail --user scripted --max-models 6
```

Then use `--agent auto-free` which loads the saved best model.

## Model Recommendations

| Model | Provider | Tool Calling | Speed | Notes |
|-------|----------|-------------|-------|-------|
| qwen3:8b | Ollama | Native | Fast | Best local tool use |
| llama3.1:8b | Ollama | Native | Fast | Good general perf |
| gemini-1.5-flash | Gemini | Native | Very fast | Free tier available |
| llama-3.1-8b-instant | Groq | Native | Fastest | Groq free tier |
| gemma3:4b | Ollama | ReAct | Very fast | Lowest memory |
