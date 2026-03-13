# 🌐 Network Access Configuration

**Last Updated:** March 12, 2026

## ✅ Current Network Configuration

Your FastAPI server is running and accessible at:

| Access Method | URL | Status |
|--------------|-----|--------|
| **Localhost** | http://localhost:8000 | ✅ Working |
| **Network IP** | http://10.54.6.204:8000 | ✅ Working |
| **Android Emulator** | http://10.0.2.2:8000 | ✅ Always use this |

---

## 📱 Access from Your Kotlin Frontend

### For Android Emulator:
```kotlin
const val BASE_URL = "http://10.0.2.2:8000"
```

### For Physical Device (Same WiFi):
```kotlin
const val BASE_URL = "http://10.54.6.204:8000"
```

---

## 🧪 Quick Test

Open these URLs in any browser on the same network:

- **API Docs**: http://10.54.6.204:8000/docs
- **Health Check**: http://10.54.6.204:8000/health
- **OpenAPI Spec**: http://10.54.6.204:8000/openapi.json

---

## 🔧 Troubleshooting

### IP Address Changed?
Your IP address can change when:
- You restart your router
- You switch WiFi networks
- DHCP lease expires

**To get your current IP:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

**Update the**Update the**Update the**Update the**Update thete **Update the**Update the**Updatig.json` - Update `network.baseUrl**Update the**Update the**Update the**Update the*s runni**Update the**Update the http://localhost:8000/health
   ```

2. **Check if port 8000 is listening on all interfaces:**
   ```bash
   lsof -i :8000 -P
   ```
   Should show `*:8000` (not `127.0.0.1:8000`   Sho**Check macOS Firewall:**
   - Go to System Preferences → Security & Privacy → Firewall
   - If enabled, allow Python to accept incoming connections

4. **Test from another device:**
   ```bash
   curl http://10.54.6.204:8000/health
   ```

---

## 📝 Server Configuration

The server is configured to bind to all network interfaces in `backend_api/main.py`:

```python
uvicorn.run(
    "backend_api.main:app",
    host="0.0.0.0",  # ← Listens on all interfaces
    port=8000,
    reload=True,
)
```

This allows access from:
- localhost (127.0.0.1)
- Network IP (10.54.6.204)
- Any device on the same network

---

**Need help?** Check the full setup guide in [API_CLIENT_SETUP.md](API_CLIENT_SETUP.md)
