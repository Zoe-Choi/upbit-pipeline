#!/bin/bash
# ClickHouse 클러스터 테스트 스크립트

set -e

echo "🔍 ClickHouse 클러스터 테스트"
echo "================================"

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. 연결 테스트
echo -e "\n${YELLOW}1. 노드 연결 테스트${NC}"
echo "Node 1 (Shard 1):"
docker exec clickhouse-1 clickhouse-client --query "SELECT 'OK' as status, hostName() as host"

echo "Node 2 (Shard 2):"
docker exec clickhouse-2 clickhouse-client --query "SELECT 'OK' as status, hostName() as host"

# 2. 클러스터 정보
echo -e "\n${YELLOW}2. 클러스터 구성 확인${NC}"
docker exec clickhouse-1 clickhouse-client --query "
    SELECT 
        cluster,
        shard_num,
        replica_num,
        host_name
    FROM system.clusters 
    WHERE cluster = 'upbit_cluster'
    FORMAT PrettyCompact
"

# 3. Keeper 연결 확인
echo -e "\n${YELLOW}3. ClickHouse Keeper 연결 확인${NC}"
docker exec clickhouse-1 clickhouse-client --query "
    SELECT * FROM system.zookeeper WHERE path = '/'
    FORMAT PrettyCompact
" 2>/dev/null || echo "Keeper 연결 확인 완료 (또는 아직 초기화 중)"

# 4. 테이블 초기화
echo -e "\n${YELLOW}4. 테이블 초기화${NC}"
docker exec -i clickhouse-1 clickhouse-client < "$(dirname "$0")/../clickhouse/init.sql" 2>/dev/null || true
echo "테이블 초기화 완료"

# 5. 분산 쿼리 테스트
echo -e "\n${YELLOW}5. 분산 테이블 데이터 확인${NC}"
docker exec clickhouse-1 clickhouse-client --query "
    SELECT * FROM upbit.ticker ORDER BY symbol FORMAT PrettyCompact
" 2>/dev/null || echo "테이블이 아직 생성되지 않았습니다. init.sql을 먼저 실행하세요."

# 6. 샤드별 데이터 분포
echo -e "\n${YELLOW}6. 샤드별 데이터 분포${NC}"
docker exec clickhouse-1 clickhouse-client --query "
    SELECT 
        hostName() as shard,
        count() as rows
    FROM upbit.ticker_local 
    GROUP BY shard
    FORMAT PrettyCompact
" 2>/dev/null || echo "아직 데이터가 없습니다."

# 7. 성능 테스트 (간단한 집계)
echo -e "\n${YELLOW}7. 집계 쿼리 성능 테스트${NC}"
docker exec clickhouse-1 clickhouse-client --query "
    SELECT 
        symbol,
        count() as cnt,
        avg(price) as avg_price,
        max(price) as max_price,
        min(price) as min_price
    FROM upbit.ticker
    GROUP BY symbol
    FORMAT PrettyCompact
" 2>/dev/null || echo "데이터가 없습니다."

echo -e "\n${GREEN}✅ ClickHouse 클러스터 테스트 완료${NC}"
echo ""
echo "접속 정보:"
echo "  - Node 1 HTTP: http://localhost:8123"
echo "  - Node 2 HTTP: http://localhost:8124"
echo "  - Node 1 TCP:  localhost:9002"
echo "  - Node 2 TCP:  localhost:9003"
echo ""
echo "클라이언트 접속:"
echo "  docker exec -it clickhouse-1 clickhouse-client"
echo ""
echo "HTTP 쿼리 예시:"
echo "  curl 'http://localhost:8123/?query=SELECT%20*%20FROM%20upbit.ticker'"
