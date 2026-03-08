import sys
import os
import streamlit as st
import json
import google.generativeai as genai
import re
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from summarizer import get_summary
from planner import generate_world_plan

st.set_page_config(
    page_title="AI 소설 집필실",
    page_icon="🖋️",
    layout="wide" # 👈 핵심: 화면을 좌우로 꽉 채웁니다.
)


# --- [1. 파일 경로 설정] ---
CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"
HISTORY_FILE = "story_log.json"

CURRENT_MODEL = 'gemini-3.1-flash-lite-preview'

DEFAULT_PROMPT_TEMPLATE = """
    당신은 전문 소설 기획자입니다. 입력된 핵심 키워드를 바탕으로 소설의 '메인 플롯'과 '디테일한 세계관'을 생성하세요.
    [절대 포함 금지 키워드] : {exclude_keywords}
    
    [핵심 키워드]: {keywords}
    
    [요청 사항]:
    1. 주인공의 이름: 이름을 임의로 만들지 마십시오. 주인공은 반드시 '{{{{user}}}}'라고 지칭하십시오.
    2. 메인 플롯: '{{{{user}}}}'의 목표와 갈등, 그리고 3개 이상의 이벤트를 흥미진진하게 구성할 것. 단 결말은 생성하지 않는다.
    3. 상세 세계관: 단순히 개념적인 설명이 아니라, 주 무대가 되는 '특정 지역명', '지형적 특징', '그 지역만의 고유한 사회 분위기'를 디테일하게 묘사할 것.
    4. 지리적 요소: 주요 장소 3~4곳의 명칭과 특징을 포함하여 세계지도를 그리듯 상세히 설명할 것.
    5. 주의: 제외 키워드와 관련된 설정(예: 현대물인데 갑자기 마법이나 초과학이 나오는 등)은 절대 넣지 마십시오.
    
    형식:
    [PLOT]
    (내용 작성)
    [WORLD]
    (내용 작성)
    """


# --- [2. 데이터 관리 함수] ---
# [환경 체크] 클라우드 배포 상태인지 확인
IS_CLOUD = os.path.exists("/app") or "STREAMLIT_RUNTIME_ENV" in os.environ

if st.session_state.get("show_load_success"):
    st.toast("✅ 불러오기 완료!")
    del st.session_state["show_load_success"] # 한 번 띄웠으면 삭제

def load_json(file_path, default_data):
    if IS_CLOUD:
        return default_data
    if not os.path.exists(file_path):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=4, ensure_ascii=False)
            return default_data
        except:
            return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default_data

def save_json(file_path, data):
    if IS_CLOUD:
        return
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- [API 및 모델 설정 로직] ---
def get_model_info():
    active_key = None
    source = None

    if st.session_state.get("user_api_key"):
        active_key = st.session_state.user_api_key
        source = "user"
    elif IS_CLOUD:
        active_key = st.secrets.get("GEMINI_API_KEY")
        if active_key: source = "cloud"
    
    if not active_key and not IS_CLOUD:
        config_data = load_json(CONFIG_FILE, {"api_key": ""})
        active_key = config_data.get('api_key', '')
        if active_key: source = "local"

    if active_key:
        try:
            genai.configure(api_key=active_key)
            return genai.GenerativeModel(CURRENT_MODEL), source, active_key
        except:
            return None, None, None
    return None, None, None

model, key_source, active_api_key = get_model_info()

# 메시지 이력 로드
if "messages" not in st.session_state:
    history_data = load_json("story_log.json", {"chat_history": []})
    st.session_state.messages = history_data.get("chat_history", [])

# --- [3. 텍스트 스타일 처리 함수] ---
def format_novel_text(text):
    s = st.session_state.settings
    base_faded = s.get("ui_faded_color", "#C8C8C8")
    faded_color = base_faded + "B3" if len(base_faded) == 7 else base_faded
    dialogue_color = s.get("ui_dialogue_color", "#FFFFFF")
    margin_val = s.get("ui_dialogue_margin", 22)
    
    text = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #FFD700;">\1</b>', text)

    def replace_dialogue(match):
        return (f'<div style="color: {dialogue_color}; font-size: 1.1em; font-weight: bold; '
                f'margin: {margin_val}px 0; line-height: 1.6; display: block;">{match.group(0)}</div>')
    
    content = re.sub(r'"(.*?)"', replace_dialogue, text)
    content = content.replace('\n', '<br>')
    content = re.sub(r'(<br>\s*){3,}', '<br><br>', content)

    return f'<div style="color: {faded_color}; line-height: 1.8; word-break: keep-all;">{content}</div>'

# --- [4. 초기 설정 및 로드] ---
config_data = load_json(CONFIG_FILE, {"api_key": ""})

# 🔥 기본 설정값에 '메인 플롯(main_plot)'과 주인공 '성격(personality)'이 확실히 추가되었습니다.
default_settings = {
    "main_plot": "주인공이 역경을 딛고 성장하여 최종 목표를 달성하는 이야기",
    "world_setting": "새로운 세계관을 입력하세요.",
    "writing_style": "담백한 구어체",
    "player_setting": {"name": "주인공", "personality": "정의롭고 끈기 있음", "current_status": "건강함", "inventory": []},
    "characters": {},
    "restrict_player_dialogue": True,
    "story_summary": "이야기가 이제 시작되었습니다.",
    "ui_faded_color": "#BBBBBB",
    "ui_dialogue_color": "#FFFFFF",
    "ui_dialogue_margin": 22,
    "custom_rules": "1. 모든 대화문은 반드시 '\"이름: 대사\"' 형식을 지키고, 이름과 대사 사이에 줄바꿈을 하지 마세요.\n2. 장면 서술보다는 인물 간의 대화 비중을 30% 이상으로 유지하여 생동감을 높이세요.\n3. **절대 사용자가 방금 입력한 대사를 그대로 반복하거나 따라하지 마십시오.**\n4. NPC는 자신만의 개성 있는 말투로 새로운 질문이나 반응을 던져 대화를 유도하세요.",
    "custom_sys_inst": "당신은 소설 작가입니다. 아래의 [현재 줄거리]를 인지하고 다음 이야기를 전개하세요. 아래 지침에 따라 **최소 3~5문단 이상의 풍부한 분량**으로 서술하세요.\n"
}

if "settings" not in st.session_state:
    if IS_CLOUD:
        st.session_state.settings = default_settings.copy()
    else:
        st.session_state.settings = load_json(SETTINGS_FILE, default_settings)

if "messages" not in st.session_state:
    if IS_CLOUD:
        st.session_state.messages = []
    else:
        history_data = load_json(HISTORY_FILE, {"chat_history": []})
        st.session_state.messages = history_data.get("chat_history", [])

current_key = st.session_state.get("user_api_key")
if not current_key and not IS_CLOUD:
    config_data = load_json(CONFIG_FILE, {"api_key": ""})
    current_key = config_data.get('api_key', '')
    if current_key:
        st.session_state.user_api_key = current_key

if current_key:
    try:
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(CURRENT_MODEL)
    except Exception as e:
        st.sidebar.error(f"❌ API 연결 오류: {e}")
        model = None
else:
    st.sidebar.warning("🔑 API 키를 설정 탭에서 입력해주세요.")
    model = None

# --- [5. 사이드바 구성] ---
# (사이드바에서는 복잡한 소설 설정을 빼고, 상태 확인과 도구 위주로 개편했습니다)
with st.sidebar:
    st.header("🎮 시스템 메뉴")
    tab_info, tab_npc, tab_inv, tab_cmd, tab_help, tab_set = st.tabs(["👤 정보", "👥 인물", "🎒 가방", "⌨ 도구", "📖 가이드", "⚙️ 설정"])

    with tab_info:
        s = st.session_state.settings
        st.info(f"**주인공:** {s['player_setting']['name']}\n\n**상태:** {s['player_setting']['current_status']}")
        st.divider()
        st.subheader("🛠️ API 상태")
        
        if active_api_key:
            if key_source == "user":
                st.success("✅ 개인 API 키 연결됨")
            elif key_source == "cloud":
                st.info("☁️ 공용 API 키 연결됨")
            elif key_source == "local":
                if IS_CLOUD: st.warning("⚠️ 서버 설정 키 연결됨")
                else: st.success("🏠 로컬 API 키 연결됨")
        else:
            st.error("❌ API 키 설정 필요")

        st.divider()
        st.subheader("💾 데이터 관리")
        if IS_CLOUD: st.info("클라우드 모드: 브라우저 종료 시 내용이 사라지니 꼭 저장하세요!")
    
        uploaded_file = st.file_uploader("소설 파일(.json) 불러오기", type="json")
        if uploaded_file is not None:
            if "last_uploaded_file" not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
                try:
                    uploaded_data = json.load(uploaded_file)
                    if "chat_history" in uploaded_data:
                        st.session_state.messages = uploaded_data["chat_history"]
                    if "settings" in uploaded_data:
                        st.session_state.settings.update(uploaded_data["settings"])
                    if "api_key" in uploaded_data and uploaded_data["api_key"]:
                        st.session_state.user_api_key = uploaded_data["api_key"]
                        if not IS_CLOUD:
                            save_json(CONFIG_FILE, {"api_key": uploaded_data["api_key"]})
            
                    st.session_state.last_uploaded_file = uploaded_file.name
                    st.session_state.show_load_success = True
                    st.rerun() 
                except Exception as e:
                    st.error(f"오류 발생: {e}")

        has_messages = len(st.session_state.get("messages", [])) > 0
        combined_data = {
            "chat_history": st.session_state.get("messages", []),
            "settings": st.session_state.get("settings", {}),
            "api_key": st.session_state.get("user_api_key", "")
        }
        json_string = json.dumps(combined_data, indent=4, ensure_ascii=False)

        st.download_button(
            label="📥 현재 이야기 & 설정(API키포함) 저장",
            data=json_string, file_name="my_novel_full_data.json", mime="application/json",
            use_container_width=True, disabled=not has_messages
        )
        if not has_messages: st.caption("※ 소설 내용이 있어야 활성화됩니다.")
        st.divider()
        st.markdown("""<div style="text-align: center; padding: 10px; background-color: rgba(100, 100, 100, 0.1); border-radius: 10px;">
            <span style="font-size: 2em;">🐱</span><br><b style="color: #FFD700;">제작자: POTG</b></div>""", unsafe_allow_html=True)

    with tab_npc:
        st.subheader("주변 인물 호감도")
        chars = st.session_state.settings.get('characters', {})
        visible_chars = {k: v for k, v in chars.items() if v.get('is_visible', True)}
        if not visible_chars: st.caption("발견된 인물이 없습니다.")
        for cid, info in visible_chars.items():
            with st.expander(f"📍 {info['name']}"):
                like = info.get('likability', 0)
                st.write(f"**호감도:** {like}/100")
                st.progress(like / 100)
                st.caption(info.get('description', ''))

    with tab_inv:
        st.subheader("🎒 소지품")
        inv = st.session_state.settings['player_setting'].get('inventory', [])
        with st.form("add_item", clear_on_submit=True):
            ni = st.text_input("아이템 추가")
            if st.form_submit_button("획득") and ni:
                inv.append(ni)
                st.session_state.settings['player_setting']['inventory'] = inv
                save_json(SETTINGS_FILE, st.session_state.settings)
                st.rerun()
        for i, item in enumerate(inv):
            c1, c2 = st.columns([4, 1])
            c1.write(f"- {item}")
            if c2.button("🗑️", key=f"inv_{i}"):
                inv.pop(i)
                st.session_state.settings['player_setting']['inventory'] = inv
                save_json(SETTINGS_FILE, st.session_state.settings)
                st.rerun()

    with tab_cmd:
        st.subheader("📝 소설 도구")
        st.code("!추가 인물명", language=None)
        st.divider()
        if st.session_state.messages:
            full_text = "".join([f"[{'주인공' if m['role']=='user' else 'AI 작가'}]\n{m['parts'][0]}\n\n" for m in st.session_state.messages])
            st.download_button("📥 현재 이야기 다운로드(txt)", data=full_text, file_name="story.txt")
        st.divider()
        if st.button("🔄 이야기 초기화"):
            st.session_state.messages = []; save_json(HISTORY_FILE, {"chat_history": []}); st.rerun()

    with tab_help:
        st.markdown("""
            ### 📝 기본 입력 규칙
            1. **`* *` (별표)**: 상황 설명이나 지문을 작성할 때 사용합니다.  
               *예: *갑자기 하늘에서 번개가 친다.* *
            2. **`" "` (따옴표)**: 캐릭터의 직접적인 대사를 표현할 때 사용합니다.  
               *예: "누구냐, 거기 숨어있는 놈이!"*
            3. **평문**: 상황 묘사, 캐릭터의 감정, 행동 등을 자유롭게 서술하세요. AI가 문맥을 파악해 이어갑니다.
            4. {{user}}: 이는 메인플롯과 세계관에서 유저(주인공)을 뜻 합니다. 주인공 이름을 직접 입력해도 되지만, 재사용성을 위해 해당 문자로 처리합니다.

            ---

            ### 💾 데이터 보관 주의사항
            4. **휘발성 주의**: 본 앱은 보안을 위해 브라우저를 완전히 닫으면 모든 정보가 초기화됩니다.  
               - **[ℹ️ 정보]** 탭에서 **'현재 이야기 & 설정 저장'** 버튼을 수시로 눌러 `.json` 파일을 소장하세요.
            5. **텍스트 추출**: 소설의 본문 텍스트만 깔끔하게 따로 받고 싶다면 **[🛠️ 도구]** 탭의 **'현재 이야기 다운로드'** 기능을 이용하세요.

            ---

            ### 🔑 개인 API 키 사용 안내 (Gemini 1.5 Flash 기준)
            6. **무료 티어 이용 제한**:
                - **분당 호출 수 (RPM)**: 최대 **15회** (1분에 15번 이상 전송 시 잠시 차단됩니다.)
                - **일일 호출 수 (RPD)**: 최대 **1,500회**
                - **분당 토큰 수 (TPM)**: 최대 **100만 토큰** (소설 내용이 극도로 길어지면 영향이 있을 수 있습니다.)
    
            > **Tip**: AI의 답변이 끊기거나 에러가 난다면, 보통 1분당 호출 제한(RPM)에 걸린 경우입니다. 약 1분 뒤에 다시 시도해 주세요.
        """)

        st.info("💡 파일을 다시 불러오면 이전의 집필 상태와 API 키까지 모두 자동으로 복구됩니다.")


    with tab_set:
        st.subheader("🔑 API 보안/설정")
        display_key = st.session_state.get("user_api_key", "")
        if not display_key and not IS_CLOUD:
            config_data = load_json(CONFIG_FILE, {"api_key": ""})
            display_key = config_data.get('api_key', '')
            if display_key: st.session_state.user_api_key = display_key

        user_key_input = st.text_input("Gemini API Key", value=display_key, type="password")
        col_key1, col_key2 = st.columns([1, 2])
        with col_key1:
            if st.button("✅ 적용", use_container_width=True):
                if user_key_input:
                    st.session_state.user_api_key = user_key_input
                    if not IS_CLOUD: save_json(CONFIG_FILE, {"api_key": user_key_input})
                    st.rerun()
        with col_key2:
            st.link_button("🔑 Google AI Studio", "https://aistudio.google.com/app/apikey", use_container_width=True)


        st.divider()
        if st.button("🔍 내 API 사용 가능 모델 확인"):
            if not active_api_key:
                st.error("먼저 API 키를 입력해주세요.")
            else:
                try:
                    genai.configure(api_key=active_api_key)
                    models = genai.list_models()
                    
                    st.write("### 📋 호출 가능한 모델 리스트")
                    available_models = []
                    for m in models:
                        if 'generateContent' in m.supported_generation_methods:
                            # 'models/' 접두사를 제외한 순수 ID만 추출
                            model_id = m.name.replace('models/', '')
                            available_models.append(model_id)
                            st.code(model_id) # 복사하기 편하게 코드 블록으로 출력
                    
                    st.success(f"총 {len(available_models)}개의 모델을 찾았습니다.")
                except Exception as e:
                    st.error(f"모델 목록을 가져오는 중 오류 발생: {e}")

        st.divider()
        st.subheader("🎨 디자인 및 프롬프트 제어")
        with st.form("advanced_settings"):
            s = st.session_state.settings
            col1, col2 = st.columns(2)
            new_faded = col1.color_picker("지문 색상", value=s.get("ui_faded_color", "#C8C8C8"))
            new_dialogue = col2.color_picker("대화문 색상", value=s.get("ui_dialogue_color", "#FFFFFF"))
            new_margin = st.slider("대화문 위아래 여백 (px)", 0, 50, s.get("ui_dialogue_margin", 22))
            st.divider()
            new_sys_inst = st.text_area("시스템 지침 (Sys_Inst)", value=s.get("custom_sys_inst", ""), height=100)
            new_rules = st.text_area("핵심 규칙 (Rules)", value=s.get("custom_rules", ""), height=150)
            if st.form_submit_button("고급 설정 저장"):
                s.update({"ui_faded_color": new_faded, "ui_dialogue_color": new_dialogue, "ui_dialogue_margin": new_margin, "custom_sys_inst": new_sys_inst, "custom_rules": new_rules})
                save_json(SETTINGS_FILE, s)
                st.rerun()


# ==========================================
# --- [6. 메인 화면 탭 분리 (기획실 / 집필실)] ---
# ==========================================
# 1. 상단 고정 영역 (타이틀 및 탭)
header_container = st.container()
with header_container:
    st.title("✨ AI 소설 스튜디오")
    tab_setup, tab_write = st.tabs(["📋 기획 및 설정", "🖋️ 소설 집필실"])


# ------------------------------------------
# 📋 1. 기획 및 설정 탭 (메인 화면)
# ------------------------------------------
with tab_setup:
    st.info("💡 여기에 작성된 내용은 AI가 이야기를 전개할 때 절대적으로 참고하는 '뼈대'가 됩니다. 언제든 수정 가능합니다.")

    st.subheader("🤖 키워드로 세계관 자동생성")
    
    with st.expander("✨ 키워드로 메인 플롯 & 세계관 생성 (주의! 기존 내용은 사라집니다)", expanded=False):
        col_k1, col_k2 = st.columns([2, 2])
        keywords = col_k1.text_input("핵심 키워드", placeholder="예: 현대, 강남, 검사, 복수")
        exclude_keywords = col_k2.text_input("제외 키워드", placeholder="예: SF, 판타지, 마법, 좀비")

        # 작가님이 직접 수정할 수 있는 프롬프트 편집기
        user_prompt_custom = st.text_area(
            "AI에게 내리는 상세 지시서 (편집 가능)", 
            value=DEFAULT_PROMPT_TEMPLATE, 
            height=300,
            help="이 내용을 수정하여 AI의 기획 스타일을 바꿀 수 있습니다. {keywords}와 {exclude_keywords}는 위 입력창의 값으로 치환됩니다. [PLOT]과 [WORLD] 이 글자들은 수정금지! 해당글자 아래의 글들이 자동으로 하단의 플롯과 세계관에 들어갑니다"
        )
        
        if st.button("🪄 자동 생성 (자동생성 시 무료API는 토큰 제한으로 약 1분간 소설이 정상 출력되지 않을 수 있습니다.)", use_container_width=True):
            if not keywords:
                st.warning("핵심 키워드를 입력해주세요.")
            else:
                with st.spinner("AI 기획자가 금기 사항을 피해 세계를 설계 중입니다..."):
                    final_prompt = user_prompt_custom.format(
                        keywords=keywords, 
                        exclude_keywords=exclude_keywords
                    )
                    
                    # planner.py의 수정된 함수 호출 (제외 키워드 전달)
                    result, error = generate_world_plan(active_api_key, final_prompt, CURRENT_MODEL)
                    if error:
                        st.error(f"오류 발생: {error}")
                    else:
                        st.session_state.settings['main_plot'] = result['plot']
                        st.session_state.settings['world_setting'] = result['world']
                        st.success("원치 않는 설정을 제외한 새로운 세계관이 설계되었습니다!")
                        st.rerun()

    st.divider()
    
    with st.form("story_master_plan"):
        s = st.session_state.settings
        
        # 1. 핵심 플롯 (결말 지정)
        st.subheader("🎯 1. 메인 플롯 (스토리의 최종 목표)")
        new_plot = st.text_area("이 소설이 최종적으로 향해가는 결말이나 핵심 갈등을 적어주세요. (AI가 이야기가 산으로 가는 것을 막아줍니다.)", 
                                value=s.get('main_plot', '주인공이 역경을 딛고 성장하는 이야기'), height=100)
        
        # 2. 세계관
        st.subheader("🌍 2. 세계관 및 배경")
        new_w = st.text_area("시대적 배경, 마법 규칙, 세력 구도 등을 상세히 적어주세요.", 
                             value=s.get('world_setting', ''), height=150)
        
        # 3. 주인공 및 문체 설정
        st.subheader("👤 3. 주인공 및 문체 설정")
        col1, col2, col3 = st.columns(3)
        p_n = col1.text_input("주인공 이름", value=s['player_setting'].get('name', ''))
        p_desc = col2.text_input("주인공 성격/특징", value=s['player_setting'].get('personality', ''))
        new_s = col3.text_input("문체 설정", value=s.get('writing_style', '담백한 구어체'))
        res_d = st.checkbox("주인공 대사 자동 생성 금지 (추천)", value=s.get('restrict_player_dialogue', True))
        
        if st.form_submit_button("💾 소설 마스터 플랜 저장", use_container_width=True):
            s.update({
                "main_plot": new_plot,
                "world_setting": new_w,
                "writing_style": new_s,
                "restrict_player_dialogue": res_d
            })
            s['player_setting']['name'] = p_n
            s['player_setting']['personality'] = p_desc
            save_json(SETTINGS_FILE, s) 
            st.success("✨ 소설의 뼈대가 저장되었습니다! 우측 상단의 '소설 집필실' 탭으로 이동해 글을 써보세요.")
            st.rerun()

    st.divider()

    # 조연(NPC) 관리를 메인 화면으로 이동
    st.subheader("👥 주요 등장인물 관리 (NPC)")
    
    with st.expander("➕ 새 인물 수동 추가", expanded=False):
        with st.form("manual_npc_add", clear_on_submit=True):
            m_name = st.text_input("인물 이름")
            m_desc = st.text_area("인물 설명 (성격, 역할, 주인공과의 관계 등)")
            if st.form_submit_button("추가하기"):
                chars = st.session_state.settings.get('characters', {})
                new_id = f"npc_{int(re.sub(r'[^0-9]', '', max(chars.keys(), default='npc_0'))) + 1}"
                st.session_state.settings['characters'][new_id] = {"name": m_name, "description": m_desc, "likability": 0, "is_visible": True}
                save_json(SETTINGS_FILE, st.session_state.settings)
                st.rerun()
    
    # 기존 인물 리스트 및 수정 폼
    char_dict = st.session_state.settings.get('characters', {})
    if char_dict:
        # 딕셔너리의 키를 리스트로 변환해 순회 (삭제 시 안전함)
        cids = list(char_dict.keys())
        cols = st.columns(3)
        
        for idx, cid in enumerate(cids):
            info = char_dict[cid]
            with cols[idx % 3].expander(f"⚙️ {info['name']}", expanded=False):
                # 폼으로 감싸서 입력 도중 새로고침 방지
                with st.form(key=f"form_{cid}"):
                    u_name = st.text_input("이름", value=info['name'])
                    u_desc = st.text_area("설명", value=info['description'])
                    u_vis = st.checkbox("사이드바 호감도 표시", value=info.get('is_visible', True))
                    
                    c1, c2 = st.columns(2)
                    
                    if c1.form_submit_button("💾 저장"):
                        # 직접 업데이트
                        st.session_state.settings['characters'][cid] = {
                            "name": u_name,
                            "description": u_desc,
                            "is_visible": u_vis
                        }
                        save_json(SETTINGS_FILE, st.session_state.settings)
                        st.success("수정 완료!")
                        st.rerun()

                    # 삭제 버튼은 폼 밖에 두거나, 혹은 별도 처리 (폼 안의 버튼은 하나만 가능하므로)
                if st.button("🗑️ 삭제", key=f"u_r_{cid}", use_container_width=True):
                    del st.session_state.settings['characters'][cid]
                    save_json(SETTINGS_FILE, st.session_state.settings)
                    st.rerun()
    else:
        st.caption("아직 등록된 등장인물이 없습니다.")


# ------------------------------------------
# 🖋️ 2. 소설 집필실 탭 (메인 화면)
# ------------------------------------------
# ------------------------------------------
# 🖋️ 2. 소설 집필실 탭 (메인 화면)
# ------------------------------------------
with tab_write:

    # 1. 메시지 출력 전용 컨테이너 (위치 고정)
    chat_scroll_area = st.container(height=600, border=False)

    # 2. 저장된 메시지들 화면에 출력 (기존 기록 루프)
    with chat_scroll_area:
        if "display_count" not in st.session_state:
            st.session_state.display_count = 30

        all_messages = st.session_state.messages
        total_msgs = len(all_messages)

        if total_msgs > st.session_state.display_count:
            if st.button("🔼 이전 기록 더보기", use_container_width=True):
                st.session_state.display_count += 30
                st.rerun()

        start_idx = max(0, total_msgs - st.session_state.display_count)
        msgs_to_show = all_messages[start_idx:]

        for i, msg in enumerate(msgs_to_show):
            real_idx = start_idx + i
            with st.chat_message(msg["role"]):
                st.markdown(format_novel_text(msg["parts"][0]), unsafe_allow_html=True)
                c1, c2 = st.columns([11, 1])
                if c2.button("🗑️", key=f"del_{real_idx}"):
                    st.session_state.messages.pop(real_idx)
                    save_json(HISTORY_FILE, {"chat_history": st.session_state.messages})
                    st.rerun()

    # 3. 채팅 입력 및 로직 처리
    if prompt := st.chat_input("행동이나 대사를 입력하세요..."):
        # [기존 기능 A] API 키 설정 확인
        if model is None:
            st.error("⚠️ API 키가 설정되지 않았습니다! 왼쪽 '⚙️ 설정' 사이드바에서 Gemini API 키를 입력해 주세요.")
        
        # [기존 기능 B] !추가 명령어 처리
        elif prompt.startswith("!추가 "):
            try:
                name_part = prompt.replace("!추가 ", "").strip()
                chars = st.session_state.settings.get('characters', {})
                new_id = f"npc_{int(re.sub(r'[^0-9]', '', max(chars.keys(), default='npc_0'))) + 1}"
                st.session_state.settings['characters'][new_id] = {
                    "name": name_part, "description": "새로 추가된 인물", "likability": 0, "is_visible": True
                }
                save_json(SETTINGS_FILE, st.session_state.settings)
                st.toast(f"✨ {name_part}가 추가되었습니다!")
                st.rerun()
            except:
                st.error("명령어 형식을 확인하세요. (예: !추가 홍길동)")

        # [기존 기능 C] 일반 소설 집필 및 요약 로직
        else:
            # 1. 사용자 입력을 세션에 먼저 저장
            st.session_state.messages.append({"role": "user", "parts": [prompt]})
            save_json(HISTORY_FILE, {"chat_history": st.session_state.messages})

            # 2. 화면 출력 시작
            with chat_scroll_area:
                # --- [수정 포인트 1]: 사용자 말풍선을 여기서 완벽히 끝냅니다 ---
                with st.chat_message("user"):
                    st.markdown(format_novel_text(prompt), unsafe_allow_html=True)
                
                # --- [수정 포인트 2]: 위 'with' 블록 밖에서 AI 말풍선을 새로 시작합니다 ---
                with st.chat_message("model"):
                    with st.spinner("작가가 집필 중..."):
                        ss = st.session_state.settings
                        p = ss['player_setting']
                        current_story = ss.get('story_summary', "이제 막 이야기가 시작되었습니다.")
                        char_info = "\n".join([f"- {v['name']}: {v['description']} (호감도: {v.get('likability', 0)})" for v in ss['characters'].values() if v.get('is_visible', True)])

                        # 최근 맥락 (사용자 입력 포함)
                        history_to_send = st.session_state.messages[-6:]
                        restriction_rule = f"1. [절대 금지]: 주인공({p['name']})의 직접적인 대사, 생각, 감정 묘사를 당신(AI)이 임의로 작성하지 마십시오." if ss.get('restrict_player_dialogue', True) else f"1. [허용]: 주인공({p['name']})의 대사를 상황에 맞게 작성하세요."

                        sys_inst = (
                            f"{ss.get('custom_sys_inst', '당신은 소설 작가입니다.')}\n\n"
                            f"[메인 플롯 (스토리 최종 목표)]: {ss.get('main_plot', '')}\n\n"
                            f"[현재 줄거리]: {current_story}\n\n"
                            f"[주인공 정보]: 이름 - {p['name']}, 성격 및 특징 - {p.get('personality', '')}\n\n"
                            f"[조연/NPC 정보]:\n{char_info}\n\n"
                            f"[제한 사항]:\n{restriction_rule}\n\n"
                            f"[핵심 규칙]:\n{ss.get('custom_rules', '')}\n\n"
                            f"문체: {ss.get('writing_style', '')}\n"
                            f"세계관: {ss.get('world_setting', '').replace('{{user}}', p['name'])}\n"
                        )
                        
                        try:
                            # 3. Gemini 대화 시작 (방금 넣은 prompt 제외하고 전송하거나 history 구조에 맞게 조정)
                            chat = model.start_chat(history=history_to_send[:-1])
                            response_stream = chat.send_message(f"{sys_inst}\n\n입력: {prompt}", stream=True)
                            
                            # 실시간 스트리밍 출력
                            full_response = st.write_stream(chunk.text for chunk in response_stream)
                        
                            # 4. AI 답변 저장
                            st.session_state.messages.append({"role": "model", "parts": [full_response]})
                            save_json(HISTORY_FILE, {"chat_history": st.session_state.messages})
                            
                            # [기존 기능 D] 10회 주기 줄거리 요약 트리거
                            if len(st.session_state.messages) % 10 == 0:
                                # AI 말풍선 밖에서 요약 진행 여부를 보여주기 위해 spinner 활용
                                with st.spinner("중간 줄거리 정리 중..."):
                                    old_summary = ss.get('story_summary', "")
                                    new_summary = get_summary(active_api_key, st.session_state.messages, old_summary, CURRENT_MODEL)
                                    st.session_state.settings['story_summary'] = new_summary
                                    save_json(SETTINGS_FILE, ss)
                            
                            # 5. 최종 완료 후 리런
                            st.rerun()

                        except Exception as e:
                            st.error(f"오류: {e}")


