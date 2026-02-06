#!/bin/bash
# ============================================
# Flink Streaming Jobs Launcher
# Executes Flink SQL to create tables and start jobs
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SQL_DIR="$PROJECT_ROOT/flink-sql"

echo "========================================="
echo "Flink Streaming Jobs Setup"
echo "========================================="

# Check if Flink JobManager is running
if ! docker ps | grep -q flink-jobmanager; then
    echo "Error: flink-jobmanager container is not running"
    echo "Please start it with: docker compose up -d flink-jobmanager"
    exit 1
fi

echo "Copying SQL files to Flink container..."
docker cp "$SQL_DIR" flink-jobmanager:/opt/flink/

# Download required JARs if not present
echo "Checking for required Flink connectors..."

FLINK_LIB="/opt/flink/lib"
JARS=(
    "https://repo1.maven.org/maven2/org/apache/paimon/paimon-flink-1.18/0.7.0-incubating/paimon-flink-1.18-0.7.0-incubating.jar"
    "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar"
    "https://repo1.maven.org/maven2/org/apache/paimon/paimon-s3/0.7.0-incubating/paimon-s3-0.7.0-incubating.jar"
    "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar"
    "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar"
)

for jar_url in "${JARS[@]}"; do
    jar_name=$(basename "$jar_url")
    echo "Checking: $jar_name"
    
    # Check if jar exists in container
    if ! docker exec flink-jobmanager test -f "$FLINK_LIB/$jar_name"; then
        echo "Downloading: $jar_name"
        docker exec flink-jobmanager wget -q -P "$FLINK_LIB" "$jar_url" || {
            echo "Warning: Failed to download $jar_name"
        }
    else
        echo "Already exists: $jar_name"
    fi
done

echo ""
echo "========================================="
echo "Flink SQL files are ready!"
echo ""
echo "To start interactive SQL client:"
echo "  docker exec -it flink-jobmanager /opt/flink/bin/sql-client.sh"
echo ""
echo "Then execute SQL files in order:"
echo "  1. CREATE CATALOGS:     SOURCE '/opt/flink/flink-sql/01-create-catalogs.sql';"
echo "  2. CREATE KAFKA TABLES: SOURCE '/opt/flink/flink-sql/02-create-kafka-sources.sql';"
echo "  3. CREATE PAIMON TABLES: SOURCE '/opt/flink/flink-sql/03-create-paimon-tables.sql';"
echo "  4. START STREAMING JOBS: SOURCE '/opt/flink/flink-sql/04-streaming-jobs.sql';"
echo ""
echo "Or run queries:"
echo "  SOURCE '/opt/flink/flink-sql/05-queries.sql';"
echo "========================================="
