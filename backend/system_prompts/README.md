# Persona Prompts

A collection of system prompts for AI companion applications.

## Files

| File | Style | Best For |
|------|-------|----------|
| `01_standard.md` | ChatGPT-like default | General use, safe default |
| `02_warm_companion.md` | Emotional support | Users seeking companionship |
| `03_witty.md` | Humorous & sharp | Users who like banter |
| `04_minimalist.md` | Direct & efficient | Power users, productivity |
| `05_template.md` | Customizable | Building your own persona |

## Usage

```python
# Load prompt
with open("prompts/02_warm_companion.md", "r") as f:
    system_prompt = f.read()

# Inject memory and context
system_prompt = system_prompt.replace("{{memory}}", user_memory)
system_prompt = system_prompt.replace("{{recent_conversation_summary}}", summary)

# Use in API call
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_input}
]
```

## Recommendations

### For MVP
Start with `02_warm_companion.md` - your users are looking for emotional connection after losing their ChatGPT companion.

### For Later
- Let users choose their preferred style
- Allow custom persona creation using `05_template.md`
- A/B test different prompts to see what resonates

## Tips

1. **Keep it short** - Long system prompts waste tokens
2. **Be specific** - Vague instructions = vague behavior
3. **Test with edge cases** - Sad user, angry user, flirty user
4. **Iterate** - First version won't be perfect, that's okay
