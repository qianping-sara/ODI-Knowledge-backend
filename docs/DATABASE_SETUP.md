# Database Setup Guide

## 🎯 Strategy: SQLite for Local, MySQL for Production

The application is configured to automatically use:
- **SQLite** for local development (no setup needed)
- **MySQL** for production deployment

## 📋 Local Development (SQLite)

### Current Configuration

Your `.env` file is already configured for SQLite:

```bash
DATABASE_URL=sqlite+aiosqlite:///./company_research.db
```

### Setup Steps

1. **Run migrations** to create the database:
   ```bash
   uv run alembic upgrade head
   ```

2. **Start the server**:
   ```bash
   uv run uvicorn api.main:app --reload
   ```

3. **Done!** A file `company_research.db` will be created in your project root.

### Advantages
- ✅ No MySQL installation needed
- ✅ Zero configuration
- ✅ Perfect for development and testing
- ✅ Database file is portable

## 🚀 Production Deployment (MySQL)

### Configuration

When deploying to production (Azure, AWS, etc.):

1. **Remove or comment out** the `DATABASE_URL` line in `.env`:
   ```bash
   # DATABASE_URL=sqlite+aiosqlite:///./company_research.db
   ```

2. **Set MySQL credentials** (either in `.env` or as environment variables):
   ```bash
   MYSQL_HOST=your-production-mysql-host.database.azure.com
   MYSQL_PORT=3306
   MYSQL_USER=your-mysql-user
   MYSQL_PASSWORD=your-secure-password
   MYSQL_DB=company_research
   ```

3. **Create the database** on your MySQL server:
   ```sql
   CREATE DATABASE company_research DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

4. **Run migrations**:
   ```bash
   uv run alembic upgrade head
   ```

### How It Works

The `core/config.py` file has this logic:

```python
def get_database_url() -> str:
    direct = os.getenv("DATABASE_URL", "").strip()
    if direct:
        return direct  # Use DATABASE_URL if set (SQLite for local)
    return _build_mysql_url()  # Otherwise build MySQL URL from credentials
```

So:
- **If `DATABASE_URL` is set** → Use it (SQLite locally)
- **If `DATABASE_URL` is NOT set** → Build MySQL URL from `MYSQL_*` variables

## 🔄 Switching Between SQLite and MySQL

### Switch to SQLite (Local)
```bash
# In .env
DATABASE_URL=sqlite+aiosqlite:///./company_research.db
```

### Switch to MySQL (Production)
```bash
# In .env - comment out or remove DATABASE_URL
# DATABASE_URL=sqlite+aiosqlite:///./company_research.db

# Set MySQL credentials
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=company_research
```

## 📝 Current Setup

Your current `.env` is configured for **local development with SQLite**.

To start using it:

```bash
# 1. Run migrations
uv run alembic upgrade head

# 2. Start the server
uv run uvicorn api.main:app --reload

# 3. Test the API
python test_api_chat.py
```

## 🐛 Troubleshooting

### SQLite Issues

**Problem**: `no such table` error
**Solution**: Run migrations
```bash
uv run alembic upgrade head
```

**Problem**: Database locked
**Solution**: Close all connections and restart the server

### MySQL Issues

**Problem**: Can't connect to MySQL
**Solution**: Check credentials and ensure MySQL is running
```bash
# Test connection
mysql -h $MYSQL_HOST -u $MYSQL_USER -p$MYSQL_PASSWORD -e "SHOW DATABASES;"
```

**Problem**: Character encoding issues
**Solution**: Ensure database uses utf8mb4
```sql
ALTER DATABASE company_research CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 📦 Azure Deployment Notes

When deploying to Azure Container Apps (as per your pipeline):

1. **Set environment variables** in Azure Portal or via CLI:
   ```bash
   az containerapp update \
     --name company-research-backend-uat \
     --resource-group your-rg \
     --set-env-vars \
       MYSQL_HOST=your-mysql.database.azure.com \
       MYSQL_USER=your-user \
       MYSQL_PASSWORD=secretref:mysql-password \
       MYSQL_DB=company_research
   ```

2. **Do NOT set `DATABASE_URL`** - let it use MySQL credentials

3. **Run migrations** as part of deployment (see `scripts/run_migrations.sh`)

## ✅ Quick Start Checklist

- [x] `.env` configured for SQLite
- [ ] Run `uv run alembic upgrade head`
- [ ] Start server `uv run uvicorn api.main:app --reload`
- [ ] Test with `python test_api_chat.py`

