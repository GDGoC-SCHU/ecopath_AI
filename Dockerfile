# Python 공식 이미지 사용
FROM python:3.12

# 작업 디렉토리 설정
WORKDIR /app

# 로컬 코드 복사
COPY . /app

# 필요한 라이브러리 설치
RUN pip install FastAPI
RUN pip install requests
RUN pip install dotenv
RUN pip install uvicorn
RUN pip install google-genai
RUN pip install google.generativeai

# 컨테이너 실행 시 기본적으로 실행할 명령 설정# FastAPI 실행
CMD ["uvicorn", "routes:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
