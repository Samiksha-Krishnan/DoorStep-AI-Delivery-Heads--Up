# Architecture

## Components
| Component | File | Responsibility |
|---|---|---|
| Web UI | `static/index.html` | Message input, delivery list, risk display, shows alerts |
| API server | `app.py` | REST endpoints, SQLite access, serves the UI |
| Parser | `parser.py` | Turns free text into courier, item, OTP, date, window, status |
| Risk model | `ml.py` | Trains and loads the classifier, predicts delay probability, explains it |
| Scheduler | `app.py` (`check_due`) | Every 30 s creates morning and lead-time alerts, optionally sends Telegram |
| Database | `doorstep.db` | Tables: `deliveries`, `alerts`, `settings` |

## Alert flow
1. User adds a delivery. The server predicts risk and stores it.
2. The scheduler checks every 30 s. If the delivery is today and it is after 7 AM, it creates a "Delivery today" alert once.
3. When the time left before the window start is within the user's warning time, it creates a "Get ready" alert once.
4. The browser polls `/api/alerts`, shows a notification, and the alert is marked seen. Telegram receives the same text if configured.

## Data model
- `deliveries(id, uid, item, courier, otp, start, end, risk, label, why, done, n1, n2)`; `n1` and `n2` record that each alert was sent.
- `alerts(id, uid, title, body, seen)`
- `settings(uid, lead)`

## Model
Features: courier (one-hot), weekday, start hour, window length, rain mm. Target: delayed (0/1).
Pipeline: `ColumnTransformer(OneHotEncoder) + classifier`, saved with joblib.
