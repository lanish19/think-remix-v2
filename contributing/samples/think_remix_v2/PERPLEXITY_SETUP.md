# Perplexity API Setup for THINK Remix v2.0

## Overview

THINK Remix v2.0 now supports **Perplexity API** as an alternative to Google Search. Perplexity provides real-time web search with AI-powered synthesis and citations, which can be more effective for research queries.

## Configuration

### 1. Set Perplexity API Key

```bash
export PERPLEXITY_API_KEY="your-perplexity-api-key"
```

Get your API key from: https://www.perplexity.ai/settings/api

### 2. Configure Search Provider

Edit `config.yaml`:

```yaml
search:
  # Search provider: 'google' or 'perplexity'
  provider: 'perplexity'  # Change to 'google' to use Google Search
  
  # Perplexity-specific settings
  perplexity:
    model: 'llama-3.1-sonar-large-128k-online'
    max_results: 10
    temperature: 0.2
```

### 3. Available Perplexity Models

- `llama-3.1-sonar-large-128k-online` (default) - Best for real-time search
- `llama-3.1-sonar-small-128k-online` - Faster, lower cost
- `llama-3.1-sonar-huge-128k-online` - Most capable

See Perplexity docs for latest models: https://docs.perplexity.ai/

## Usage

The search tool is automatically selected based on your configuration. Agents that use search (`gather_insights_agent`, `conduct_research_agent`) will use the configured provider.

### Switching Between Providers

**To use Perplexity:**
```yaml
search:
  provider: 'perplexity'
```

**To use Google Search:**
```yaml
search:
  provider: 'google'
```

## Benefits of Perplexity

1. **Real-time Search**: Accesses current web information
2. **Citations**: Provides source citations for all claims
3. **Synthesized Answers**: AI-powered synthesis of search results
4. **Better for Research**: More effective for complex research queries

## Benefits of Google Search

1. **Native Integration**: Built into Gemini models
2. **No API Key Needed**: Uses Google Cloud credentials
3. **Faster**: Direct model integration
4. **Cost**: Included with Gemini API usage

## Code Changes

The implementation:
- Created `perplexity_tool.py` - Perplexity API integration
- Updated `config.yaml` - Added search configuration
- Updated `config_loader.py` - Added search provider properties
- Updated `agent.py` - Dynamic search tool selection

## Testing

To test Perplexity integration:

```python
from contributing.samples.think_remix_v2.perplexity_tool import _search_perplexity

result = _search_perplexity("What is the latest research on AI safety?")
print(result)
```

## Troubleshooting

### Error: PERPLEXITY_API_KEY not set
- Make sure you've exported the environment variable
- Check that the API key is valid

### Error: API request failed
- Verify your API key has credits/quota
- Check Perplexity API status: https://status.perplexity.ai/

### Want to use both providers?
- You can modify the code to use both tools
- Or switch providers based on query type

## API Costs

Perplexity API pricing:
- Pay-per-use model
- Check current pricing: https://www.perplexity.ai/pricing

Google Search:
- Included with Gemini API usage
- No additional cost
