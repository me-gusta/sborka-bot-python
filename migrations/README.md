# Database Migrations

## Adding first_name and last_name fields to users table

### On Ubuntu/Linux:

```bash
# Navigate to project directory
cd /path/to/sborka-bot-python

# Run migration
sqlite3 bot_database.db < migrations/add_user_name_fields.sql
```

### Alternative method (interactive):

```bash
sqlite3 bot_database.db
```

Then in SQLite prompt:
```sql
ALTER TABLE users ADD COLUMN first_name VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN last_name VARCHAR(255) NULL;
.quit
```

### Verify migration:

```bash
sqlite3 bot_database.db "PRAGMA table_info(users);"
```

You should see `first_name` and `last_name` columns in the output.

