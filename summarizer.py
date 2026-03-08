import google.generativeai as genai

def get_summary(api_key, messages, current_summary="", model_name='gemini-3.1-flash-lite-preview'):
    """
    지금까지의 대화와 기존 줄거리를 바탕으로 새로운 줄거리 요약을 생성합니다.
    """
    if not api_key:
        return current_summary

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        # 최근 맥락 추출 (메시지 구조에 맞춰 안전하게 추출)
        recent_context = ""
        for m in messages[-10:]: # 너무 길면 요약 호출 자체가 실패하므로 10개로 제한
            role = "주인공" if m['role'] == 'user' else "AI 작가"
            content = m['parts'][0]
            recent_context += f"[{role}]: {content}\n"
        
        prompt = f"""
        소설 편집 보조로서 아래 내용을 바탕으로 '소설 줄거리'를 핵심 위주로 업데이트하세요.
        
        [기존 줄거리]:
        {current_summary if current_summary else "이야기 시작 단계입니다."}
        
        [최근 대화 내용]:
        {recent_context}
        
        [지침]:
        1. 인물 관계 변화, 아이템, 위치, 진행 사건 중심으로 요약.
        2. AI 작가가 일관성을 유지하도록 간결하게 작성.
        3. 반드시 3~5문장 내외로 요약.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # 에러 발생 시 기존 요약을 유지하여 중단 방지
        print(f"요약 생성 중 오류 발생: {e}")
        return current_summary
