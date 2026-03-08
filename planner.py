import google.generativeai as genai

def generate_world_plan(active_api_key, keywords):
    """
    사용자가 입력한 키워드를 바탕으로 디테일한 메인 플롯과 세계관을 생성합니다.
    """
    if not active_api_key:
        return None, "API 키가 설정되지 않았습니다."

    genai.configure(api_key=active_api_key)
    model = genai.GenerativeModel('models/gemini-flash-latest')

    prompt = f"""
    당신은 전문 소설 기획자입니다. 입력된 키워드를 바탕으로 소설의 '메인 플롯'과 '디테일한 세계관'을 생성하세요.
    
    [입력 키워드]: {keywords}
    
    [요청 사항]:
    1. 메인 플롯: 주인공의 목표와 갈등, 예상 결말을 흥미진진하게 구성할 것.
    2. 상세 세계관: 단순히 '지구' 같은 넓은 개념이 아니라, 사건의 주 무대가 되는 '특정 지역명', '지형적 특징', '정치/사회 상황'을 아주 디테일하게 묘사할 것.
    3. 지리적 요소: 주요 장소 3~4곳의 명칭과 특징을 포함하여 세계지도를 그리듯 묘사할 것.
    
    형식:
    [PLOT]
    (플롯 내용 작성)
    [WORLD]
    (상세 세계관 배경 작성)
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text
        
        # 데이터 파싱
        plot_content = ""
        world_content = ""
        
        if "[PLOT]" in result and "[WORLD]" in result:
            plot_content = result.split("[PLOT]")[1].split("[WORLD]")[0].strip()
            world_content = result.split("[WORLD]")[1].strip()
        else:
            plot_content = result  # 파싱 실패 시 전체 출력
            
        return {"plot": plot_content, "world": world_content}, None
    except Exception as e:
        return None, str(e)
