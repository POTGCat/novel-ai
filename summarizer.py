import google.generativeai as genai

def get_summary(api_key, messages, current_summary=""):
    """
    지금까지의 대화와 기존 줄거리를 바탕으로 새로운 줄거리 요약을 생성합니다.
    """
    if not api_key:
        return current_summary

    genai.configure(api_key=api_key)
    # 요약에는 성능이 좋고 저렴한 flash 모델을 사용합니다.
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 요약을 위한 프롬프트 구성
    # 너무 많은 대화를 보내면 요약 단계에서 쿼터가 터질 수 있으므로 최근 15개 정도만 참고합니다.
    recent_context = "\n".join([f"[{m['role']}]: {m['parts'][0]}" for m in messages[-15:]])
    
    prompt = f"""
    당신은 소설 작가의 편집 보조입니다. 아래 내용을 바탕으로 지금까지의 '소설 줄거리'를 핵심 위주로 업데이트하세요.
    
    [기존 줄거리]:
    {current_summary if current_summary else "이야기 시작 단계입니다."}
    
    [최근 대화 내용]:
    {recent_context}
    
    [지침]:
    1. 인물들의 관계 변화, 획득한 아이템, 현재 위치, 진행 중인 사건을 중심으로 요약하세요.
    2. 다음 대화에서 AI 작가가 일관성을 유지할 수 있도록 간결하게 작성하세요.
    3. 3~5문장 내외로 요약하세요.
    
    업데이트된 줄거리 요약:
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"요약 생성 중 오류 발생: {e}")
        return current_summary