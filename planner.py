import google.generativeai as genai

def generate_world_plan(active_api_key, full_prompt, model_name='gemini-3.1-flash-lite-preview', style_traits=None):
    """
    사용자가 입력한 키워드를 바탕으로 디테일한 메인 플롯과 세계관을 생성합니다.
    """
    if not active_api_key:
        return None, "API 키가 설정되지 않았습니다."

    genai.configure(api_key=active_api_key)
    model = genai.GenerativeModel(model_name)

    try:
        response = model.generate_content(full_prompt)
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
