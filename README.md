# 🏃 **StrideSync** – Collaborative & Competitive Running Tracker

## 🌱 Summary
**StrideSync** is a running tracker designed for **both solo runners and groups** who want to track their progress, encourage one another, or engage in friendly competition. Whether you're training alone, running with friends, or participating in a workplace challenge — StrideSync lets you **track, visualise, and share your journey**.

Ideal for everything from casual 5k runners to half-marathon prep and charity group runs.

---

## 🔧 Core Features

| Feature | Description |
|--------|-------------|
| **Run Tracking Log** | Tracking log of distance, pace, route, time, and calories. |
| **Solo and Group Modes** | Run alone or opt into:<br>  - **Challenges** (e.g. "Run 50km in June")<br>  - **Cumulative Goals** (e.g. "Team Abtrace runs to London" - 400km together) |
| **Live Leaderboards** | Ranks participants by total distance, improvement, consistency, etc. |
| **Team Chat / Motivations** | Lightweight group chat with daily reminders, encouragement GIFs, or milestone celebrations. |
| **Progress Heatmaps** | Visualise when and how often you run — can be shared with others. |
| **Goal Setting** | Personal goals with progress tracking:<br>  - Daily, weekly, or event-based<br>  - Optional nudges or reminders |
| **Integrated Challenges** | Monthly themed runs (e.g. "Sunrise Streak Week", "Marathon in a Month") that anyone can join. |
| **Custom Groups** | Private groups for clubs, companies, families, or friends — invite-only with shared stats. |
| **Wearable Sync** | Connect with Garmin, Apple Watch, Fitbit, or Strava for automatic import. |

---

## 🎯 Target Users

- **Casual runners** who want simple but motivating progress tracking.
- **Fitness clubs or charity teams** coordinating joint goals.
- **Corporate wellness programs** aiming to build engagement.
- **Marathon or half-marathon trainees** needing weekly structure.
- **Friends & families** who live in different places but run together virtually.

---

## 💸 Monetisation Strategy

### 1. **Freemium App Model**
- Free version includes:
  - Run tracking
  - Join public challenges
  - Personal stats
- Premium (~€3.99/month) unlocks:
  - Create private groups
  - Advanced analytics (pace trends, weather, effort)
  - Audio cues + coaching tips
  - Custom challenges
  - Export features

### 2. **Corporate/Group Tier**
- Charge companies or clubs:
  - Admin dashboard for HR/organisers
  - Private group with branding
  - Weekly summary reports
  - Wellbeing stats dashboard

### 3. **Merch + Partner Rewards**
- Discount codes from sportswear/gear brands.
- Branded medals or virtual trophies for challenge winners.

---

## 🧩 Differentiators

| Feature | Why It Stands Out |
|---------|-------------------|
| Group-first design | Built around the *shared journey*, not just individual logging. |
| Friendly, not intense | No judgment-based gamification — celebrates consistency. |
| Custom challenges | More engaging than generic weekly summaries. |
| Visual UX | Emphasis on story-style recaps, heatmaps, and simple shareable graphics. |

---

## 📣 Growth Strategy

- **Partner with running clubs** and wellness communities.
- **Offer limited-time “Team Challenges”** in cities or schools.
- **Create a community leaderboard by region** — “Top Running Teams in Dublin”.
- **User-generated challenge formats**: “My Running Crew” with Instagram share templates.
- **TikTok + IG ads** showing story-like “Day 12 of 21” journeys.

---

## ⚠️ Risks & Considerations

- **Privacy and location sensitivity**: Must allow for private mode and hide routes.
- **Low retention risk** post-challenge: Retention tools like streaks, unlockable content, and visual progress needed.
- **Hardware syncing bugs**: Careful testing across Garmin/Apple/Fitbit ecosystem is essential.

---

## 🚀 Future Expansion

- **Walking mode** for inclusive challenges with all fitness levels.
- **Team vs Team competitions** for workplaces, schools, or cities.
- **Virtual races** with real-time map tracking.
- **Social accountability layer**: Let people pledge runs to charity or unlock rewards for consistency.
- **API + leaderboard widget** for embedding group stats into websites or Slack.

---

## Design inspiration
https://preview.themeforest.net/item/sociohub-social-media-marketing-agency-elementor-template-kit/full_screen_preview/53438282

## Coding notes

flask run


html:

```
{% if title %}
<title>{{ title }} - Microblog</title>
{% else %}
<title>Welcome to Microblog!</title>
{% endif %}
```

```
{% for post in posts %}
<div><p>{{ post.author.username }} says: <b>{{ post.body }}</b></p></div>
{% endfor %}
```

{% block content %}{% endblock %}

