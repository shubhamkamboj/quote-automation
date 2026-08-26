# Hindi Life Quotes → Instagram Automation

A Python + GitHub Actions automation for a Hindi diary-style Instagram page.

## Daily flow

1. Read the optional local `priority.txt` file.
2. If it contains a non-empty, non-comment line, use the **first one** as today's content.
3. If `priority.txt` is empty, missing, or contains only comments, call the **Gemini API** for a fresh Hindi life quote.
4. Randomly select one of the 10 diary templates.
5. Write the selected content onto the template.
6. Generate a caption containing the **exact same quote** plus 5 relevant/popular hashtags.
7. Commit the generated image to GitHub.
8. Publish the image to Instagram.
9. If a priority line was used, remove that line **only after Instagram confirms successful publication**, then commit the updated `priority.txt`.
10. If Gemini quote generation, image generation, GitHub, Instagram, or another required workflow step fails, the workflow fails and the configured SMTP alert attempts to email you.

The priority feature is only an **addon**. There is no Google Sheet and no Google API involved.

## Folder structure

```text
ig-quotes-automation/
├── app/
│   ├── generate.py
│   ├── quote_source.py
│   ├── publish_instagram.py
│   └── notify_failure.py
├── data/
│   └── state.json
├── fonts/
│   └── NotoSansDevanagari-Regular.ttf
├── templates/
│   ├── template-01.jpg ... template-10.jpg
├── generated/
├── priority.txt
├── .github/workflows/daily-instagram.yml
├── .env.example
├── requirements.txt
└── README.md
```

## 1. Diary templates

Replace the starter images with your final 10 diary backgrounds:

`templates/template-01.jpg` through `templates/template-10.jpg`

Recommended size: **1080 × 1800** (3:5).

The generator covers the sample quote area near the bottom and writes the dynamic Hindi content there.

## 2. Priority addon — `priority.txt`

This is intentionally just a **plain text/notepad file**. You do not need Google Sheets, Google credentials, or another service.

Example:

```text
आज मेरी बेटी के लिए एक खास संदेश ❤️
आज का यह संदेश पहले publish होना चाहिए।
एक और priority quote...
```

The workflow reads the file from top to bottom and uses the **first non-empty line**.

Lines beginning with `#` are treated as comments and ignored. The starter file already contains comments explaining how to use it.

### Behavior

```text
priority.txt has content
        ↓
Use first priority line
        ↓
Generate diary image
        ↓
Publish to Instagram
        ↓
Success?
   YES         NO
    ↓           ↓
Remove line   Keep line
    ↓           ↓
Commit file   Workflow fails
```

If `priority.txt` is:

- missing → **no error**, Gemini is used
- empty → **no error**, Gemini is used
- comments only → **no error**, Gemini is used
- contains multiple items → first item is used; remaining items stay for future days

A priority line is removed only after successful Instagram publication, so a failed publish does not lose the priority content.

## 3. Gemini quote generation

The daily quote is generated fresh by Gemini. There is no `quotes.json` fallback.

Default model:

```text
gemini-2.5-flash
```

Configure it with the GitHub secret `GEMINI_MODEL` if you want another supported model.

The prompt requests:

- exactly one quote
- Hindi / Devanagari
- 8–22 words
- natural, emotional, positive and meaningful
- diary / life-quotes style
- no hashtags
- no emojis
- no attribution
- no explanation
- no recent-quote repetition

If Gemini fails, returns empty text, or returns invalid output, `generate.py` exits with an error. That makes the GitHub Actions workflow fail and triggers the failure-email step.

## 4. Instagram secrets

Create these GitHub repository secrets:

```text
IG_USER_ID
IG_ACCESS_TOKEN
META_API_VERSION=v25.0
HASHTAGS=#LifeQuotes #HindiQuotes #Zindagi #PositiveThoughts #DailyQuotes
```

Do not put access tokens directly in the repository.


## Instagram caption

The Instagram caption is automatically built as:

```text
EXACT SAME QUOTE AS THE IMAGE

#Hashtag1 #Hashtag2 #Hashtag3 #Hashtag4 #Hashtag5
```

By default, Gemini generates 5 relevant/popular hashtags for the day's quote. Hashtag generation is **best-effort** and will not fail the post; if it fails, the fallback hashtags are used. This keeps the main requirement—publishing the quote—reliable.

For a fixed hashtag set instead, create the GitHub secret:

```text
AUTO_HASHTAGS=false
HASHTAGS=#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes
```

Note: automatically generated hashtags are relevant/popular suggestions, not a guarantee of real-time Instagram trending status. True real-time trending detection would require a separate live trend source.

## 5. Failure email

The workflow has a final `if: failure()` step. If any earlier step fails—including Gemini quote generation—it attempts to send an email.

Configure:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-smtp-or-app-password
ALERT_FROM_EMAIL=your-email@example.com
ALERT_TO_EMAIL=where-you-want-the-alert@example.com
```

If SMTP secrets are missing, the workflow still fails normally; only the email notification is skipped.

## 6. Automatic schedule

The workflow runs every day at **7:30 PM IST**:

```yaml
- cron: '0 14 * * *'
```

GitHub Actions cron uses UTC.

You can also run it manually from:

`GitHub → Actions → Daily Hindi Quote → Run workflow`

## 7. Important GitHub image URL detail

Instagram needs a publicly accessible HTTPS image URL.

The workflow commits the generated image first and then uses the **new commit SHA** to construct the raw GitHub URL:

```text
https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/COMMIT_SHA/generated/quote-YYYYMMDD-HHMMSS.jpg
```

The repository/image URL therefore needs to be publicly accessible to Instagram. For a private repository, use public object storage such as S3 or Cloudinary instead.

## 8. Local test

```bash
python -m venv .venv

# Windows
.venv\\Scripts\\activate

pip install -r requirements.txt
```

Set your Gemini key and run:

```bash
set GEMINI_API_KEY=YOUR_KEY
python app/generate.py
```

To test priority behavior, put a line into `priority.txt` and run the same command. The generated image will use that line instead of calling Gemini.

The generated image appears in:

```text
generated/quote-YYYYMMDD-HHMMSS.jpg
```


## Dynamic publishing controls

The workflow is now controlled through **GitHub Repository Variables**:

| Variable | Example | Meaning |
|---|---:|---|
| `ENABLE_IMAGE_POSTS` | `true` | `true` publishes image posts; `false` skips image publishing |
| `IMAGE_POST_COUNT` | `2` | Number of image posts to publish |
| `REEL_POST_COUNT` | `3` | Number of Reel posts to publish |
| `USE_GEMINI_IMAGE` | `true` | `true` generates the visual background with Gemini; `false` uses `templates/` |
| `GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image` | Gemini image model |

### How image/reel counts work

The automation generates `max(IMAGE_POST_COUNT, REEL_POST_COUNT)` content items.

For example:

```text
ENABLE_IMAGE_POSTS=true
IMAGE_POST_COUNT=2
REEL_POST_COUNT=4
```

Result:

```text
Content 1 → Image + Reel
Content 2 → Image + Reel
Content 3 → Reel only
Content 4 → Reel only
```

If:

```text
ENABLE_IMAGE_POSTS=false
IMAGE_POST_COUNT=4
REEL_POST_COUNT=3
```

Result:

```text
3 Reel posts
0 Image posts
```

The image is still generated locally because the Reel is created from that image; it is simply **not published as an Instagram photo**.

### Gemini-generated images

When `USE_GEMINI_IMAGE=true`, the template folder is not used. Gemini generates a fresh vertical visual background for each content item. The exact Hindi quote is then rendered on top by Pillow so the text in the published image remains deterministic and matches the caption exactly.

`GEMINI_IMAGE_MODEL` defaults to:

```text
gemini-3.1-flash-image
```

This is separate from `GEMINI_MODEL`, which continues to control quote generation.

### Recommended GitHub Repository Variables

```text
ENABLE_IMAGE_POSTS=true
IMAGE_POST_COUNT=2
REEL_POST_COUNT=2
USE_GEMINI_IMAGE=false
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
```

Change only the variables in GitHub; no workflow code change is required.

