# Hindi Life Quotes → Instagram Automation

A Python + GitHub Actions automation for a Hindi diary-style Instagram page.

## Daily flow

The workflow can publish either **one or two posts per day**:

1. Check the optional local `priority.txt` file.
2. If it contains a non-empty, non-comment line, that **priority content is always published first** on a random diary image.
3. After the priority post is successfully published, remove only that consumed priority line and commit the change.
4. Then call the **Gemini API** and generate a fresh Hindi life quote.
5. Publish that Gemini quote as the **second post of the day**.
6. If `priority.txt` is empty, missing, or contains only comments, there is no priority post; Gemini generates the day's single post.
7. Every post uses a random diary template.
8. Every caption contains the **exact same quote** shown on the image plus 5 relevant/popular hashtags.
9. If Gemini quote generation, image generation, GitHub, Instagram, or another required workflow step fails, the workflow fails and the configured SMTP alert attempts to email you.

### Daily behavior at a glance

```text
priority.txt has content
        ↓
1️⃣ Priority content → random image → Instagram
        ↓
2️⃣ Gemini quote → random image → Instagram

priority.txt is empty
        ↓
1️⃣ Gemini quote → random image → Instagram
```

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
First priority line
        ↓
Priority image → Instagram publish
        ↓
Remove that line only after success
        ↓
Gemini generates fresh quote
        ↓
Gemini image → Instagram publish
```

If `priority.txt` is:

- missing → **no error**, Gemini publishes the day's single post
- empty → **no error**, Gemini publishes the day's single post
- comments only → **no error**, Gemini publishes the day's single post
- contains multiple items → first item is published first; remaining items stay queued for future runs

A priority line is removed only after its Instagram publication succeeds. If that publication fails, the line remains in the file and the workflow stops, so the Gemini second post is **not** published.

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
