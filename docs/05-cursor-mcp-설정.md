# Cursor MCP 개발 환경 설정하기

> Model Context Protocol(MCP)로 AI 기반 개발 환경을 강화합니다.

## 시리즈 목차

1. [프로젝트 개요](./01-프로젝트-개요.md)
2. [Kafka 클러스터 구축 (KRaft 모드)](./02-kafka-클러스터-구축.md)
3. [Flink 클러스터 구축](./03-flink-클러스터-구축.md)
4. [MinIO + Apache Paimon 스토리지](./04-minio-paimon-스토리지.md)
5. **Cursor MCP 개발 환경 설정** (현재 글)

---

## MCP (Model Context Protocol)란?

### 개요

**MCP (Model Context Protocol)**는 AI 어시스턴트가 **외부 도구와 서비스에 접근**할 수 있게 해주는 프로토콜입니다. Cursor IDE에서 AI가 GitHub, 데이터베이스, 파일 시스템 등에 직접 접근할 수 있습니다.

### MCP 없이 vs MCP 사용 시

**MCP 없이:**
```
사용자: "GitHub에 커밋 푸시해줘"
AI: "터미널에서 다음 명령어를 실행하세요: git push ..."
     (사용자가 직접 실행해야 함)
```

**MCP 사용 시:**
```
사용자: "GitHub에 커밋 푸시해줘"
AI: (직접 GitHub API 호출하여 푸시 완료)
    "푸시가 완료되었습니다. PR 링크: ..."
```

### MCP 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      Cursor IDE                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   Claude AI                          │    │
│  │                                                      │    │
│  │  "GitHub 레포 목록 보여줘"                           │    │
│  │                    │                                 │    │
│  │                    ▼                                 │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │            MCP Protocol Layer               │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│GitHub Server│   │  DB Server  │   │ File Server │
│   (npx)     │   │   (npx)     │   │   (npx)     │
└─────────────┘   └─────────────┘   └─────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
    GitHub API        PostgreSQL          Local FS
```

---

## MCP 서버 종류

### 공식 MCP 서버

| 서버 | 기능 | 사용 예 |
|------|------|--------|
| **github** | GitHub API 접근 | 레포 관리, PR, 이슈 |
| **filesystem** | 로컬 파일 시스템 | 파일 읽기/쓰기 |
| **postgres** | PostgreSQL 접근 | SQL 쿼리 실행 |
| **memory** | 대화 기억 저장 | 컨텍스트 유지 |
| **puppeteer** | 브라우저 자동화 | 웹 스크래핑, 테스트 |
| **brave-search** | 웹 검색 | 정보 검색 |

### 커뮤니티/외부 MCP 서버

| 서버 | 기능 | 사용 예 |
|------|------|--------|
| **docker** | Docker 관리 | 컨테이너 조회/관리 |
| **kubernetes** | K8s 관리 | 클러스터 조회/관리 |
| **notion** | Notion API | 문서 관리 |
| **elasticsearch** | ES 검색 | 로그/데이터 검색 |
| **redis** | Redis 접근 | 캐시 조회/설정 |
| **gitlab** | GitLab API | GitLab 레포 관리 |

---

## 사전 준비

### 1. Node.js 설치

MCP 서버는 `npx`로 실행되므로 Node.js가 필요합니다.

```bash
# Homebrew로 설치
brew install node

# 버전 확인
node --version   # v18.x 이상 권장
npm --version
npx --version
```

### 2. API 키 발급

각 서비스별로 API 키가 필요합니다.

#### GitHub Personal Access Token (PAT)

1. https://github.com/settings/tokens 접속
2. "Generate new token (classic)" 클릭
3. 필요한 권한 선택:
   - `repo` (전체)
   - `read:org`
   - `read:user`
4. 토큰 복사 (한 번만 표시됨!)

#### Notion API Key

1. https://www.notion.so/my-integrations 접속
2. "New integration" 클릭
3. 이름 입력, 워크스페이스 선택
4. "Submit" → API 키 복사
5. **중요**: 연동할 페이지에서 "Connections" → 생성한 Integration 추가

#### Brave Search API Key

1. https://brave.com/search/api/ 접속
2. "Get Started" 클릭
3. 계정 생성 후 API 키 발급

---

## MCP 설정 파일 구성

### 설정 파일 위치

```
~/.cursor/mcp.json
```

### 전체 설정 예시

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxxxxxxxxxxxxxxxxxx"
      }
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "BSAxxxxxxxxxxxxxxxxxxxx"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/사용자명/dev"
      ]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "puppeteer": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-puppeteer"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_CONNECTION_STRING": "postgresql://postgres:password@localhost:5432/postgres"
      }
    },
    "docker": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-docker"]
    },
    "notion": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-notion"],
      "env": {
        "NOTION_API_KEY": "secret_xxxxxxxxxxxxxxxxxxxx"
      }
    },
    "kubernetes": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-kubernetes"]
    },
    "redis": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-redis",
        "redis://localhost:6379"
      ]
    },
    "elasticsearch": {
      "command": "npx",
      "args": ["-y", "@elastic/mcp-server-elasticsearch"],
      "env": {
        "ES_URL": "http://localhost:9200",
        "ES_API_KEY": "여기에_Elasticsearch_API_키"
      }
    },
    "gitlab": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-gitlab"],
      "env": {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "glpat-xxxxxxxxxxxxxxxxxxxx",
        "GITLAB_API_URL": "https://gitlab.com/api/v4"
      }
    }
  }
}
```

---

## 서버별 상세 설정

### 1. GitHub Server

```json
{
  "github": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxxxxxxxxxxxxxxxxxx"
    }
  }
}
```

**사용 가능한 기능:**
- 레포지토리 목록 조회
- 이슈/PR 생성 및 관리
- 파일 내용 조회
- 커밋 히스토리

**사용 예시:**
```
"내 GitHub 레포 목록 보여줘"
"upbit-pipeline 레포에 이슈 생성해줘"
"최근 커밋 5개 보여줘"
```

### 2. Filesystem Server

```json
{
  "filesystem": {
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "/Users/사용자명/dev"
    ]
  }
}
```

**마지막 인자**: 접근 허용할 디렉토리 경로

**사용 가능한 기능:**
- 디렉토리 구조 조회
- 파일 읽기/쓰기
- 파일 검색

**사용 예시:**
```
"dev 폴더의 파일 구조 보여줘"
"config.json 파일 내용 읽어줘"
```

### 3. Docker Server

```json
{
  "docker": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-docker"]
  }
}
```

**사용 가능한 기능:**
- 컨테이너 목록 조회
- 이미지 목록 조회
- 컨테이너 상태 확인

**사용 예시:**
```
"실행 중인 Docker 컨테이너 보여줘"
"kafka-1 컨테이너 상태 확인해줘"
```

### 4. Kubernetes Server

```json
{
  "kubernetes": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-kubernetes"]
  }
}
```

**요구사항**: `~/.kube/config` 파일 필요

**사용 가능한 기능:**
- Pod 목록 조회
- Service/Deployment 조회
- 네임스페이스 관리

**사용 예시:**
```
"kafka 네임스페이스의 Pod 상태 보여줘"
"모든 서비스 목록 조회해줘"
```

### 5. PostgreSQL Server

```json
{
  "postgres": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres"],
    "env": {
      "POSTGRES_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/dbname"
    }
  }
}
```

**사용 가능한 기능:**
- SQL 쿼리 실행
- 테이블 구조 조회
- 데이터 CRUD

**사용 예시:**
```
"users 테이블 구조 보여줘"
"SELECT * FROM orders LIMIT 10 실행해줘"
```

### 6. Notion Server

```json
{
  "notion": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-notion"],
    "env": {
      "NOTION_API_KEY": "secret_xxxxxxxxxxxxxxxxxxxx"
    }
  }
}
```

**중요**: API 키 발급 후, 연동할 페이지에서 Integration 연결 필요!

1. 노션 페이지 열기
2. 우측 상단 `...` → "Connections" 
3. 생성한 Integration 추가

**사용 예시:**
```
"내 노션 페이지 목록 보여줘"
"개발 일지 페이지에 내용 추가해줘"
```

### 7. Elasticsearch Server

```json
{
  "elasticsearch": {
    "command": "npx",
    "args": ["-y", "@elastic/mcp-server-elasticsearch"],
    "env": {
      "ES_URL": "http://localhost:9200",
      "ES_API_KEY": "your_api_key"
    }
  }
}
```

**사용 예시:**
```
"logs-* 인덱스에서 error 검색해줘"
"인덱스 목록 보여줘"
```

---

## 설정 적용하기

### 1. 설정 파일 저장

```bash
# 설정 파일 위치
~/.cursor/mcp.json
```

### 2. Cursor 재시작

설정 적용을 위해 Cursor IDE를 **완전히 종료 후 재시작**합니다.

```bash
# macOS에서 Cursor 완전 종료
pkill -f "Cursor"

# 다시 실행
open -a Cursor
```

### 3. MCP 연결 확인

Cursor에서 새 대화 시작 후:
```
"연결된 MCP 서버 목록 보여줘"
```

또는 우측 상단의 MCP 아이콘 확인

---

## 사용 예시

### GitHub 작업

```
사용자: "GitHub 레포 목록 보여줘"
AI: (GitHub MCP 서버 호출)
    
    📦 Your Repositories:
    1. upbit-pipeline (Private) - 업데이트: 1시간 전
    2. my-blog (Public) - 업데이트: 3일 전
    ...
```

```
사용자: "upbit-pipeline에 이번 작업 내용으로 이슈 생성해줘"
AI: (GitHub API로 이슈 생성)
    
    ✅ 이슈가 생성되었습니다!
    #12: "Flink 클러스터 구성 추가"
    https://github.com/user/upbit-pipeline/issues/12
```

### Docker 관리

```
사용자: "실행 중인 컨테이너 보여줘"
AI: (Docker MCP 서버 호출)
    
    🐳 Running Containers:
    - kafka-1 (apache/kafka:latest) - Up 2 hours
    - kafka-2 (apache/kafka:latest) - Up 2 hours
    - kafka-3 (apache/kafka:latest) - Up 2 hours
    - flink-jobmanager (flink:1.18) - Up 2 hours
    - minio (minio/minio:latest) - Up 2 hours
```

### 데이터베이스 쿼리

```
사용자: "PostgreSQL에서 최근 거래 10개 조회해줘"
AI: (PostgreSQL MCP 서버 호출)
    
    📊 Query Results (trades table):
    | id | symbol | price    | timestamp           |
    |----|--------|----------|---------------------|
    | 1  | BTC    | 50000000 | 2024-01-01 10:00:00 |
    | 2  | ETH    | 3000000  | 2024-01-01 10:00:01 |
    ...
```

---

## 문제 해결

### MCP 서버가 연결되지 않을 때

```bash
# Node.js 확인
node --version

# npx 직접 실행 테스트
npx -y @modelcontextprotocol/server-github

# Cursor 로그 확인 (macOS)
cat ~/Library/Logs/Cursor/main.log | grep -i mcp
```

### API 키 오류

1. 토큰이 만료되지 않았는지 확인
2. 필요한 권한(scope)이 있는지 확인
3. 환경 변수에 따옴표가 올바른지 확인

### 특정 서버만 안 될 때

```json
// 하나씩 테스트
{
  "mcpServers": {
    "github": { ... }
  }
}
```

서버 하나만 설정 후 테스트, 문제 없으면 하나씩 추가

---

## 보안 주의사항

### API 키 관리

```bash
# mcp.json 권한 설정
chmod 600 ~/.cursor/mcp.json

# Git에 커밋하지 않기
echo "mcp.json" >> ~/.gitignore_global
```

### 최소 권한 원칙

- GitHub: 필요한 레포에만 접근 권한
- PostgreSQL: 읽기 전용 계정 사용 고려
- Filesystem: 필요한 디렉토리만 허용

---

## 시리즈 마무리

축하합니다! 이제 완전한 데이터 파이프라인 개발 환경이 구축되었습니다.

### 구축 완료된 환경

| 구성 요소 | 상태 |
|-----------|------|
| Kafka 클러스터 (3 brokers) | ✅ |
| Flink 클러스터 (1 JM + 2 TM) | ✅ |
| MinIO 스토리지 | ✅ |
| Paimon 데이터 레이크 | ✅ |
| MCP 개발 환경 | ✅ |

### 다음으로 할 일

1. **업비트 WebSocket 연동**: 실시간 가격 데이터 수집
2. **Flink Job 작성**: 실시간 분석 로직 구현
3. **ML 파이프라인**: 가격 예측 모델 학습
4. **모니터링**: Prometheus + Grafana 구축

---

## 전체 시리즈 목차

1. [프로젝트 개요](./01-프로젝트-개요.md)
2. [Kafka 클러스터 구축 (KRaft 모드)](./02-kafka-클러스터-구축.md)
3. [Flink 클러스터 구축](./03-flink-클러스터-구축.md)
4. [MinIO + Apache Paimon 스토리지](./04-minio-paimon-스토리지.md)
5. [Cursor MCP 개발 환경 설정](./05-cursor-mcp-설정.md) (현재 글)

---

## 참고 자료

- [Model Context Protocol 공식 문서](https://modelcontextprotocol.io/)
- [Cursor MCP 가이드](https://docs.cursor.com/mcp)
- [MCP 서버 목록](https://github.com/modelcontextprotocol/servers)
