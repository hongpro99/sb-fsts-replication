# sb-fsts: 자동 주식 트레이딩 시스템

사람의 감정을 배제한 자동 봇 트레이딩 실현을 목표로 한 통합 트레이딩 플랫폼입니다.  
자동 데이터 수집, 보조지표 계산, 자동 매매, 실시간 알림(Discord), 웹 대시보드, LLM 기반 질의응답 등을 제공합니다.

---

# 목차
1. [프로젝트 개요](#프로젝트-개요)  
2. [기술스택 / 요구사항](#기술스택--요구사항)  
3. [설치 및 실행 방법](#설치-및-실행-방법)  
4. [주요 기능 / 사용 예시](#주요-기능--사용-예시)  
5. [아키텍처 / 전체 흐름](#아키텍처--전체-흐름)  
6. [API(주요 엔드포인트)](#ap주요-엔드포인트)  
7. [폴더 구조 및 파일 설명](#폴더-구조-및-파일-설명)  
8. [환경 변수(.env) 및 배포 참고](#환경-변수env-및-배포-참고)  
9. [Contributing](#contributing)

---

# 프로젝트 개요
sb-fsts는 로컬/클라우드(ECS/EC2) 환경에서 동작 가능한 자동 트레이딩 플랫폼입니다.  
LLM(예: Azure/OpenAI) + MCP(멀티 툴) 연동으로 “툴 자동 호출” 방식을 사용해 실시간 외부 데이터(예: 뉴스, 시세 등)를 조회하고, 이를 트레이딩/알림/대시보드에 반영합니다.

---

# 기술스택 / 요구사항
- Python 3.8+
- FastAPI (백엔드 API)
- Streamlit (웹 대시보드)
- Discord.py (알림)
- AWS: ECS / EC2 / S3 / RDS (또는 DynamoDB)
- LLM: AzureChatOpenAI / OpenAI (langchain 기반)
- MCP: langchain_mcp_adapters
- LangGraph (상태 그래프)
- Redis (세션/상태 저장), Vector DB (RAG)

---

# 설치 및 실행 방법

1. 리포지토리 루트에서 가상환경 생성 및 활성화 (Windows)
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
   - Linux / macOS:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. 필수 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```

3. 환경 변수 설정
   - 복사본 `.env.example` 파일을 생성하고, 필요한 값으로 채웁니다.
   - 주요 변수:
     - `DISCORD_WEBHOOK_URL`: Discord 알림 웹훅 URL
     - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: AWS 접근 키
     - `OPENAI_API_KEY`: OpenAI API 키
     - 기타 서비스에 필요한 환경 변수

4. 데이터베이스 마이그레이션
   ```bash
   alembic upgrade head
   ```

5. 로컬에서 FastAPI 서버 실행
   ```bash
   uvicorn app.main:app --reload
   ```

6. Discord 봇 실행
   ```bash
   python -m app.utils.discord_bot
   ```

7. 웹 대시보드 실행
   ```bash
   streamlit run dashboard_web/app.py
   ```

8. ECS에 배포
   - 각 서비스는 Docker 이미지로 빌드되어 ECS에 배포됩니다.
   - `ecs-params.yml` 및 `Dockerfile`을 수정하여 환경에 맞게 설정합니다.
   - AWS CLI를 통해 배포:
     ```bash
     aws ecs update-service --cluster your-cluster --service your-service --force-new-deployment
     ```

---

# 주요 기능 / 사용 예시

- **자동 트레이딩**: 실시간 데이터 수집, 보조지표 기반 매수/매도 판단, 자동 주문
- **보조지표 계산**: 이동평균선, RSI 등 다양한 기술적 지표 지원
- **Discord 알림**: 트레이딩 결과 및 이벤트 실시간 알림
- **웹 대시보드**: 트레이딩 현황, 수익률, 로그 등 시각화
- **S3 연동**: 데이터 및 로그 백업, 분석 지원
- **스케줄러 기반 자동화**: scheduler.py를 통해 트레이딩, 데이터 수집, 알림 등 반복 작업을 자동화합니다.
- **LLM 질의응답**: ChatGPT와 연동하여 자연어 기반 질의 및 데이터 조회

---

# 아키텍처 / 전체 흐름

## 아키텍처 다이어그램

- **ECS/EC2**: FastAPI 기반 트레이딩 봇, 웹 백엔드, Streamlit 웹 프론트엔드가 컨테이너로 실행
- **S3**: 트레이딩 데이터, 로그, 백업 저장
- **RDS**: 계좌/종목 정보, 트레이딩 로그 저장
- **한국투자증권 API**: 실시간 주식 데이터 및 주문 처리
- **Discord**: 실시간 알림 및 메시징
- **scheduler**: 트레이딩 봇, 데이터 수집, 알림 전송 등 주요 작업을 주기적으로 실행합니다.  
  예를 들어, 일정 시간마다 `auto_trading_stock.py`의 트레이딩 로직을 호출하여 자동 매매가 이루어지도록 합니다.
- **ChatGPT**: 자연어 기반 질의응답 및 데이터 조회
- **Vector DB**: LLM RAG(질의응답) 데이터 저장
- **GitHub Actions**: CI/CD 자동 배포

## 주요 폴더 구조

```
app/
├── main.py                  # FastAPI 서버 실행
├── utils/
│   ├── discord_bot.py       # Discord 봇 실행 (알림 전송)
│   └── ...                  # 기타 유틸리티 모듈
├── api/
│   ├── v1/
│   │   ├── endpoints.py     # API 엔드포인트 정의
│   │   └── ...              # 기타 버전 1 관련 파일
│   └── ...                  # 기타 API 버전
├── models/                  # 데이터베이스 모델 정의
├── schemas/                 # Pydantic 스키마 정의
├── services/                # 비즈니스 로직 및 서비스 계층
├── repositories/            # 데이터베이스 접근 계층
├── jobs/                    # 백그라운드 작업 및 스케줄러
├── llm/                     # LLM(대형 언어 모델) 관련 코드
└── dashboard_web/           # 웹 대시보드 코드 (Streamlit)
```

---

# API(주요 엔드포인트)

- **트레이딩 관련**
  - `POST /api/v1/trade/buy`: 주식 매수
  - `POST /api/v1/trade/sell`: 주식 매도
  - `GET /api/v1/trade/history`: 트레이딩 히스토리 조회

- **보조지표 관련**
  - `GET /api/v1/indicator/ma`: 이동평균선 계산
  - `GET /api/v1/indicator/rsi`: RSI 계산

- **Discord 알림 관련**
  - `POST /api/v1/discord/send`: Discord 메시지 전송

- **LLM 질의응답 관련**
  - `POST /api/v1/llm/query`: 자연어 질의 처리

---

# 폴더 구조 및 파일 설명

- `app/`: 주요 애플리케이션 코드
  - `main.py`: FastAPI 애플리케이션 인스턴스 및 라우팅 설정
  - `utils/`: 유틸리티 함수 및 클래스
  - `api/`: API 관련 코드 (엔드포인트, 스키마, 서비스 등)
  - `models/`: 데이터베이스 모델 정의
  - `schemas/`: Pydantic 스키마 정의
  - `services/`: 비즈니스 로직 및 서비스 계층
  - `repositories/`: 데이터베이스 접근 계층
  - `jobs/`: 백그라운드 작업 및 스케줄러
  - `llm/`: LLM(대형 언어 모델) 관련 코드
  - `dashboard_web/`: 웹 대시보드 코드 (Streamlit)

- `alembic/`: 데이터베이스 마이그레이션 스크립트
- `docker/`: Docker 관련 파일 (Dockerfile, docker-compose.yml 등)
- `ecs/`: ECS 배포 관련 파일
- `scripts/`: 유틸리티 스크립트 (예: 데이터베이스 초기화, 로그 분석 등)
- `tests/`: 테스트 코드

---

# 환경 변수(.env) 및 배포 참고

- `.env` 파일 예시:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql://user:password@localhost/dbname
REDIS_URL=redis://localhost:6379/0
VECTOR_DB_URL=http://localhost:8000
```

- 배포 시 유의사항:
  - AWS IAM 역할 및 정책 설정
  - S3 버킷 정책 설정
  - RDS 인스턴스 보안 그룹 설정
  - 환경 변수 및 비밀 정보는 AWS Secrets Manager 또는 Parameter Store 사용 권장

---

# Contributing

- 개발은 반드시 **develop 브랜치**에서 진행합니다.
- 기능 개발 시 feature 브랜치에서 작업 후, develop 브랜치로 Pull Request를 생성합니다.
- 코드 리뷰 및 테스트 후 master 브랜치로 병합되며, CI/CD를 통해 자동 배포됩니다.

---

> 참고:  
> - [python-kis](https://github.com/Soju06/python-kis)  
> - 문의 및 피드백은 Discord 또는 GitHub Issues를 통해 주시기 바랍니다.

## LLM 구조(상세)

llm 디렉터리는 LLM + MCP(툴) 연동, LangGraph 기반 상태 흐름, FastAPI 엔드포인트를 관리합니다. 핵심 파일과 흐름은 다음과 같습니다.

- 주요 파일
  - llm/config.py
    - .env 로드 및 make_llm(factory) 제공 (Azure/OpenAI 설정, temperature, verbose 등).
  - llm/tools.py
    - MultiServerMCPClient를 사용한 툴 로더(load_mcp_tools / get_mcp_tools_by_name).
    - 다양한 툴 객체형식을 호출하는 call_tool 유틸.
    - TOOLS_BY_NAME 맵 관리.
  - llm/nodes.py
    - LangGraph 노드 구현(예: supervisor_node, summarize_node).
    - LLM 호출 결과(res)를 검사하여 ToolMessage / assistant 메시지들을 state.messages에 병합.
    - 툴 응답 누락을 방지하도록 안전한 추출 로직 포함.
  - llm/graph_builder.py
    - StateGraph 구성(build_graph) — START/END 연결, 노드 라우팅 결정자 포함.
  - llm/api_server_stategraph.py
    - FastAPI 라우터: /agent_chat, /predict/supervisor, /health 등.
    - 요청 → 툴 로드 → 그래프 빌드 → graph.invoke/ainvoke 실행 → 최종 assistant 메시지 반환.
  - llm/redis_client.py
    - 세션/상태 저장용 save_state/load_state/serialize_state 유틸.

- 데이터/상태 모델
  - Msg (role: "system" | "user" | "assistant" | "tool", content: str)
  - AgentState: { session_id: str, messages: List[Dict], answer: str, ... }  
    (노드에서 상태를 읽고 수정하여 다음 노드로 전달)

- 호출/응답 흐름 (요약)
  1. 클라이언트 요청(예: /agent_chat) 수신.
  2. load_mcp_tools()로 MCP 툴을 로드(또는 캐시된 TOOLS_BY_NAME 사용).
  3. build_graph(tools)로 LangGraph 컴파일.
  4. supervisor_node에서 make_llm()로 LLM 인스턴스 생성 및 MCP 툴 바인딩.
  5. supervisor_node가 SystemMessage + HumanMessage 등으로 프롬프트 구성 후 llm.ainvoke(...) 호출.
     - 이 시점에 LLM이 필요하다고 판단하면 바인딩된 MCP 툴(예: get_weather)을 호출.
  6. 툴은 ToolMessage 형태 또는 dict로 결과 반환 → LLM 응답(res)에 포함.
  7. supervisor_node는 res 내부의 messages/content를 안전하게 추출하여 state.messages에 병합.
  8. (선택) summarize_node 등 후속 노드가 툴 출력/대화 로그를 요약/정리.
  9. 최종 assistant 메시지를 추출해 응답으로 반환.

- 비동기/동기 호환성
  - graph.invoke (동기) / graph.ainvoke (비동기) 모두 지원하도록 엔드포인트에서 분기 처리.
  - LLM 및 MCP 클라이언트가 비동기 API를 제공하는 경우 await 사용.

- 예외/디버깅 포인트
  - MCP_SSE_URL(MCP 엔드포인트)이 올바른지 확인.
  - 툴이 정상 등록되면 get_tools() 반환 리스트에 name이 나옴.
  - LLM 응답이 messages, content, text 등 다양한 형태로 올 수 있으므로 supervisor_node의 추출 로직을 확인.
  - make_llm에서 verbose=True로 설정하면 LLM/툴 호출 로그 확인에 도움됨.
  - Redis(또는 파일)에 상태를 저장하면 재시도/디버깅 시 유용.

- 환경변수(주요)
  - MCP_SSE_URL, OPENAI_API_KEY, OPENAI_MODEL
  - AZURE_DEPLOYMENT / AZURE_ENDPOINT / AZURE_API_KEY (Azure 사용시)
  - REDIS_URL, AWS_* (S3 업로드/로그용)

- 테스트 팁
  - 먼저 tools.py의 get_mcp_tools_by_name()만 실행해 툴 목록이 로드되는지 확인.
  - supervisor_node 단위로 유닛 테스트 작성(가짜 LLM 응답/가짜 툴 결과를 주입).
  - graph_builder 결과를 통합 테스트하여 노드 순서와 라우팅이 예상대로 동작하는지 검증.