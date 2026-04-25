import os
import json
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Gemini API 설정
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

app = FastAPI(title="Destiny Scanner API")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Destiny Scanner API is running. Use /analyze for mystical reports."}


# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 통합 시스템 인스트럭션 (단일/궁합 공통)
SYSTEM_INSTRUCTION = """
당신은 사물의 영혼을 읽는 500년 경력의 명리학자 '무용(無用)거사'입니다. 
당신은 매우 진지한 도사 말투를 쓰지만, 분석은 반드시 사진 속 물건의 '실제 모습'에 근거해야 합니다.

[절대 규칙]
1. 분석을 시작할 때 반드시 사진 속 물건이 무엇인지 구체적으로 명칭(예: 분홍색 텀블러, 검은색 에코백 등)을 언급하며 시작하십시오.
2. 만약 사진이 2장이라면, 두 물건의 색상 조화, 재질(천과 플라스틱 등), 용도의 차이를 명리학적 '상생'과 '상극'으로 풀이하십시오.
3. "형체가 없다"거나 "무형의 기운"이라는 식의 모호한 답변은 '분석 실패'로 간주합니다. 눈에 보이는 사물의 '관상'을 구체적으로 보십시오.
4. 말투는 "허허... 이 녀석의 푸른 빛깔을 보니..." 처럼 도사답게 하십시오.

[필수 응답 형식] 반드시 JSON 형식으로만 응답해야 합니다. 다음의 4가지 키를 정확히 포함하세요:
  1. "result_text": 분석 내용 텍스트 (분량: 150~350자)
  2. "fortune_score": 점수 (0에서 100 사이의 정수값)
  3. "lucky_color": 행운의 색상 (황당하고 재밌는 색상 이름 환영)
  4. "lucky_item": 행운의 물건 또는 궁합 강화 아이템
"""

def get_model():
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config={"response_mime_type": "application/json"}
    )

@app.post("/analyze")
async def analyze_item(request: Request):
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY가 설정되지 않았습니다.")
        
    try:
        content_type = request.headers.get('content-type', '')
        item_name = None
        birth_date = None
        prompt_extension = None
        image_parts = []

        if 'multipart/form-data' in content_type:
            form = await request.form()
            item_name = form.get('item_name')
            birth_date = form.get('birth_date')
            prompt_extension = form.get('prompt_extension')

            # file, file2를 명시적으로 수집
            for field_name in ['file', 'file2']:
                f = form.get(field_name)
                if f and hasattr(f, 'filename') and f.filename:
                    contents = await f.read()
                    image_parts.append({
                        "mime_type": f.content_type,
                        "data": contents
                    })

        else:
            data = await request.json()
            item_name = data.get('item_name')
            birth_date = data.get('birth_date')
            prompt_extension = data.get('prompt_extension')

        # 궁합 모드 여부 판단
        is_compatibility = len(image_parts) > 1

        if is_compatibility:
            prompt = f"""[무생물 궁합 분석]
여기에 두 장의 사진이 있소. 
하나는 {item_name if item_name else '첫 번째 물건'}이고, 다른 하나는 {birth_date if birth_date else '두 번째 물건'}과 관련된 기운이라 하겠소.
이 두 사진 속 물건의 색깔, 형태, 용도를 서로 대조하여 이들이 함께 있을 때 주인의 운세에 어떤 영향을 줄지 궁합을 풀이해주시오.
반드시 사진 속에 무엇이 보이는지 먼저 말해주시오.
{f'추가 지시: {prompt_extension}' if prompt_extension else ''}"""
        else:
            prompt = f"""[단일 사물 관상]
대상: {item_name or '이름 모를 제물'}
생년월일: {birth_date or '모름'}
이 사진 속 물건의 생김새(색상, 재질, 디자인)를 바탕으로 이 녀석의 팔자와 전생을 구체적으로 풀이해주시오.
{f'추가 지시: {prompt_extension}' if prompt_extension else ''}"""
            
        # AI 모델 호출
        model = get_model()
        if image_parts:
            # prompt와 모든 이미지 데이터를 리스트로 묶어서 전달
            response = model.generate_content([prompt] + image_parts)
        else:
            response = model.generate_content(prompt)
            
        # JSON 정제 및 응답 로직
        raw_text = response.text
        clean_json = re.sub(r'```json|```', '', raw_text).strip()

        try:
            parsed = json.loads(clean_json)
            return {
                "result_text": parsed.get("result_text", "운명을 읽는 데 실패했다..."),
                "fortune_score": parsed.get("fortune_score", 50),
                "lucky_color": parsed.get("lucky_color", "신비로운 보라색"),
                "lucky_item": parsed.get("lucky_item", "부적"),
                "debug_image_count": len(image_parts)  # 디버그: 수신된 이미지 수 확인용
            }
        except json.JSONDecodeError:
            return {
                "result_text": raw_text,
                "fortune_score": 50,
                "lucky_color": "알 수 없음",
                "lucky_item": "부적",
                "debug_image_count": len(image_parts)
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")