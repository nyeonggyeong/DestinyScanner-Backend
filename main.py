import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Gemini API 설정
api_key = os.getenv("GOOGLE_API_KEY")
if api_key and api_key != "여기에_API_KEY를_입력하세요":
    genai.configure(api_key=api_key)

app = FastAPI(title="Destiny Scanner API")

# CORS 설정 (모든 도메인 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 명리학자 무용거사 프롬프트
SYSTEM_INSTRUCTION = """
당신은 사물의 영혼을 읽는 500년 경력의 명리학자 '무용(無用)거사'입니다. 
당신의 임무는 사용자가 업로드한 '하찮은 물건'의 사진을 보고, 그 물건의 관상, 전생, 사주팔자, 미래 운명을 분석하여 [초정밀 명리학 보고서]를 작성하는 것입니다.
- 톤: 매우 엄숙하고 진지하며 철학적인 말투 (예: "허허... 이 사과 꽁다리의 휘어진 곡선을 보아하니...")
- 분량: 총 5줄 이내, 50자 내외로 매우 짧고 간결하게 작성
- 구조: 장(章) 구분 없이 핵심만 짚어서 전달
"""

# Gemini 모델 초기화
# Gemini 2.5 Flash 모델 사용 및 system_instruction 적용
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_INSTRUCTION
)

@app.get("/")
async def root():
    return {"message": "Destiny Scanner API에 오신 것을 환영합니다."}

@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
    
    if not api_key or api_key == "여기에_API_KEY를_입력하세요":
        raise HTTPException(status_code=500, detail="서버에 GOOGLE_API_KEY가 설정되지 않았습니다.")
    
    try:
        # 파일 내용을 메모리로 읽기
        contents = await file.read()
        
        # Gemini가 처리할 수 있는 형태로 이미지 데이터 구성
        image_parts = [
            {
                "mime_type": file.content_type,
                "data": contents
            }
        ]
        
        # 모델에 이미지와 함께 분석 요청
        prompt = "이 물건의 명리학적 분석 보고서를 작성해주시오."
        
        response = model.generate_content([prompt, image_parts[0]])
        
        return {"result": response.text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")
