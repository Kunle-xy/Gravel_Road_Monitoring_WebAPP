#!/bin/bash
# Script to apply migration 004: Add neighbor_eval fields

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    echo "Please set it with: export DATABASE_URL='postgresql://user:password@host:port/database'"
    exit 1
fi

# Apply the migration
echo "Applying migration 004_add_neighbor_eval_fields.sql..."
psql "$DATABASE_URL" -f "$(dirname "$0")/004_add_neighbor_eval_fields.sql"

if [ $? -eq 0 ]; then
    echo "Migration applied successfully!"
else
    echo "Migration failed. Please check the error messages above."
    exit 1
fi
