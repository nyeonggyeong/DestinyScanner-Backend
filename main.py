import os
import json
from fastapi import FastAPI, HTTPException, Request
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
당신의 임무는 사용자가 제공한 물건의 정보(혹은 사진)와 주인의 사주(생년월일)를 바탕으로 물건의 관상, 전생, 사주팔자, 미래 운명 및 주인과의 궁합을 분석하여 [초정밀 명리학 보고서]를 작성하는 것입니다.
- 톤: 매우 엄숙하고 진지하며 철학적인 말투 (예: "허허... 이 사과 꽁다리의 휘어진 곡선을 보아하니...")
- 분량: 분석 내용은 최소 300자 이상, 500자 내외로 상세하고 깊이 있게 작성
- 구조: 장(章) 구분 없이 핵심만 짚어서 전달
- 필수 형식: 반드시 JSON 형식으로만 응답해야 합니다. 다음의 3가지 키를 정확히 포함하세요:
  1. "result_text": 분석 내용 텍스트
  2. "score": 궁합 점수 (0에서 100 사이의 정수값)
  3. "lucky_color": 행운의 색상 문자열
"""

# Gemini 모델 초기화
# Gemini 2.5 Flash 모델 사용 및 JSON 출력 강제 설정
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={"response_mime_type": "application/json"}
)

@app.get("/")
async def root():
    return {"message": "Destiny Scanner API에 오신 것을 환영합니다."}

@app.post("/analyze")
async def analyze_item(request: Request):
    if not api_key or api_key == "여기에_API_KEY를_입력하세요":
        raise HTTPException(status_code=500, detail="서버에 GOOGLE_API_KEY가 설정되지 않았습니다.")
        
    content_type = request.headers.get('content-type', '')
    
    item_name = None
    birth_date = None
    file_contents = None
    mime_type = None
    
    try:
        # 1. FormData 파싱 (이미지가 포함된 경우)
        if 'multipart/form-data' in content_type:
            form = await request.form()
            item_name = form.get('item_name')
            birth_date = form.get('birth_date')
            file = form.get('file')
            
            if file and hasattr(file, 'filename') and file.filename:
                file_contents = await file.read()
                mime_type = file.content_type
                
        # 2. JSON 파싱 (이미지가 없는 경우)
        elif 'application/json' in content_type:
            data = await request.json()
            item_name = data.get('item_name')
            birth_date = data.get('birth_date')
            
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 데이터 형식입니다. (FormData 또는 JSON만 지원)")
            
        # 3. Gemini 프롬프트 구성 (이름과 생년월일 반영)
        prompt = "다음 정보를 바탕으로 명리학적 분석 보고서를 작성해주시오.\n"
        if item_name:
            prompt += f"- 대상 물건의 이름: {item_name}\n"
        if birth_date:
            prompt += f"- 주인의 생년월일: {birth_date}\n"
            
        # 4. 모델 호출 분기
        if file_contents:
            # 사진이 있는 경우: 텍스트 + 이미지 전달
            image_parts = [
                {
                    "mime_type": mime_type,
                    "data": file_contents
                }
            ]
            response = model.generate_content([prompt, image_parts[0]])
        else:
            # 사진이 없는 경우: 텍스트만 전달
            if not item_name and not birth_date:
                raise HTTPException(status_code=400, detail="분석할 물건의 정보나 사진을 하나 이상 제공해야 합니다.")
            response = model.generate_content(prompt)
            
        # Gemini 응답 JSON 파싱
        try:
            parsed_result = json.loads(response.text)
            return parsed_result
        except json.JSONDecodeError:
            print("Failed to parse JSON response:", response.text)
            return {
                "result_text": response.text,
                "score": 50,
                "lucky_color": "알 수 없음"
            }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")
