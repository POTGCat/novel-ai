# 스타일 가이드나 감정 묘사 사전 역할을 합니다.
def get_style_guidelines(user_traits=None):
    """
    기본 가이드라인과 사용자가 UI에서 입력한 traits를 합쳐서 반환합니다.
    """
    # 1. 기본값 (하드코딩된 고퀄리티 예시)
    guidelines = {
        "감정 표현": "기쁨은 절제하고, 고통은 감각적으로 묘사해줘. 그리고 표정 묘사를 세밀하게 넣어줘.",
        "행동 묘사": "주변 사물을 활용한 상호작용을 넣어줘. 배경묘사를 넣어줘."
    }
    
    # 2. 사용자가 UI에서 입력한 데이터(user_traits)가 있다면 덮어쓰거나 추가
    if user_traits:
        # UI에서 '감정', '행동' 키로 저장했으므로 이를 매칭
        if user_traits.get('감정'):
            guidelines["감정 표현"] = user_traits['감정']
        if user_traits.get('행동'):
            guidelines["행동 묘사"] = user_traits['행동']
            
    return guidelines
