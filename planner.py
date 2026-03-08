import google.generativeai as genai

def generate_world_plan(active_api_key, keywords, exclude_keywords="", model_name='gemini-2.5-flash-lite'):
    """
    사용자가 입력한 키워드를 바탕으로 디테일한 메인 플롯과 세계관을 생성합니다.
    """
    if not active_api_key:
        return None, "API 키가 설정되지 않았습니다."

    genai.configure(api_key=active_api_key)
    model = genai.GenerativeModel(model_name)

    # 제외 키워드가 있을 경우 프롬프트에 추가
    exclude_instruction = f"\n[절대 포함 금지 키워드]: {exclude_keywords}" if exclude_keywords else ""

    prompt = f"""
    당신은 전문 소설 기획자입니다. 입력된 핵심 키워드를 바탕으로 소설의 '메인 플롯'과 '디테일한 세계관'을 생성하세요.
    {exclude_instruction}
    
    [핵심 키워드]: {keywords}
    
    [요청 사항]:
    1. 주인공의 이름: 이름을 임의로 만들지 마십시오. 주인공은 반드시 '{{user}}'라고 지칭하십시오. 괄호가 두개 중첩되어야 합니다.
    2. 메인 플롯: 주인공의 목표와 갈등, 예상 결말을 흥미진진하게 구성할 것.
    3. 상세 세계관: 단순히 개념적인 설명이 아니라, 주 무대가 되는 '특정 지역명', '지형적 특징', '그 지역만의 고유한 사회 분위기'를 디테일하게 묘사할 것.
    4. 지리적 요소: 주요 장소 3~4곳의 명칭과 특징을 포함하여 세계지도를 그리듯 상세히 설명할 것.
    5. 주의: 제외 키워드와 관련된 설정(예: 현대물인데 갑자기 마법이나 초과학이 나오는 등)은 절대 넣지 마십시오.
    
    형식:
    [PLOT]
    (내용 작성)
    [WORLD]
    (내용 작성)
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text
        
        plot_content = ""
        world_content = ""
        
        if "[PLOT]" in result and "[WORLD]" in result:
            plot_content = result.split("[PLOT]")[1].split("[WORLD]")[0].strip()
            world_content = result.split("[WORLD]")[1].strip()
        else:
            plot_content = result
            
        return {"plot": plot_content, "world": world_content}, None
    except Exception as e:
        return None, str(e)
