import streamlit as st
from summarizer import get_summary 
import json
import os
import google.generativeai as genai
import re

# --- [1. 파일 경로 설정] ---
CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"
HISTORY_FILE = "story_log.json"

# --- [2. 데이터 관리 함수] ---
# [추가] 클라우드 여부 확인 (Streamlit Cloud는 보통 이 환경변수가 존재함)
# [환경 체크] 클라우드 배포 상태인지 확인
#IS_CLOUD = "STREAMLIT_RUNTIME_ENV" in os.environ or "STREAMLIT_SERVER_PORT" in os.environ
IS_CLOUD = os.path.exists("/app") or "STREAMLIT_RUNTIME_ENV" in os.environ

if st.session_state.get("show_load_success"):
    #st.success("✅ 소설과 설정값을 모두 불러왔습니다!")
    st.toast("✅ 불러오기 완료!")
    del st.session_state["show_load_success"] # 한 번 띄웠으면 삭제

def load_json(file_path, default_data):
    """작가님이 주신 로직을 살리되, 클라우드라면 빈 데이터를 반환하여 충돌을 방지합니다."""
    if IS_CLOUD:
        return default_data  # 클라우드에선 공용 서버 파일을 읽지 않음
    
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
    """로컬에서만 파일로 저장합니다."""
    if IS_CLOUD:
        return # 클라우드에선 서버 파일에 쓰지 않음
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- [세션 초기화 및 API 로드] ---

# 1. API 키 결정 로직
# --- [API 및 모델 설정 로직: 로컬 & 클라우드 공용] ---
def get_model_info():
    """실시간으로 키를 찾고 모델과 '출처'를 함께 반환합니다."""
    active_key = None
    source = None

    # 1. 세션 키
    if st.session_state.get("user_api_key"):
        active_key = st.session_state.user_api_key
        source = "user"
    # 2. 클라우드 시크릿
    elif IS_CLOUD:
        active_key = st.secrets.get("GEMINI_API_KEY")
        if active_key: source = "cloud"
    
    # 3. 로컬 파일
    if not active_key and not IS_CLOUD:
        config_data = load_json(CONFIG_FILE, {"api_key": ""})
        active_key = config_data.get('api_key', '')
        if active_key: source = "local"

    if active_key:
        try:
            genai.configure(api_key=active_key)
            return genai.GenerativeModel('gemini-1.5-flash'), source, active_key
        except:
            return None, None, None
    return None, None, None

# 🔥 중요: 앱 시작 시 전역 변수들에 값을 할당해줍니다.
model, key_source, active_api_key = get_model_info()



# 3. 메시지 이력 로드 (로컬은 파일에서, 클라우드는 세션에서)
if "messages" not in st.session_state:
    history_data = load_json("story_log.json", {"chat_history": []})
    st.session_state.messages = history_data.get("chat_history", [])

# --- [3. 텍스트 스타일 처리 함수] ---
def format_novel_text(text):
    """대화문 강조 및 디자인 설정을 적용하여 HTML로 변환합니다."""
    s = st.session_state.settings
    
    # 지문 색상 설정 (Hex + 투명도 70% 결합)
    base_faded = s.get("ui_faded_color", "#C8C8C8")
    faded_color = base_faded + "B3" if len(base_faded) == 7 else base_faded
    
    dialogue_color = s.get("ui_dialogue_color", "#FFFFFF")
    margin_val = s.get("ui_dialogue_margin", 22)
    
    # 1. 강조 기호 (**) 처리
    text = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #FFD700;">\1</b>', text)

    # 2. 대화문 (" ") 처리 및 여백 부여
    def replace_dialogue(match):
        return (f'<div style="color: {dialogue_color}; font-size: 1.1em; font-weight: bold; '
                f'margin: {margin_val}px 0; line-height: 1.6; display: block;">{match.group(0)}</div>')
    
    content = re.sub(r'"(.*?)"', replace_dialogue, text)
    
    # 3. 줄바꿈 및 연속 줄바꿈 정리
    content = content.replace('\n', '<br>')
    content = re.sub(r'(<br>\s*){3,}', '<br><br>', content)

    return f'<div style="color: {faded_color}; line-height: 1.8; word-break: keep-all;">{content}</div>'

# --- [4. 초기 설정 및 로드] ---
config_data = load_json(CONFIG_FILE, {"api_key": ""})

# 기본 설정값 정의
default_settings = {
    "world_setting": "새로운 세계관을 입력하세요.",
    "writing_style": "담백한 구어체",
    "player_setting": {"name": "주인공", "personality": "보통", "current_status": "건강함", "inventory": []},
    "characters": {},
    "restrict_player_dialogue": True,
    "story_summary": "이야기가 이제 시작되었습니다.",
    "ui_faded_color": "#BBBBBB",
    "ui_dialogue_color": "#FFFFFF",
    "ui_dialogue_margin": 22,
    "custom_rules": "1. 모든 대화문은 반드시 '\"이름: 대사\"' 형식을 지키고, 이름과 대사 사이에 줄바꿈을 하지 마세요.\n2. 장면 서술보다는 인물 간의 대화 비중을 30% 이상으로 유지하여 생동감을 높이세요.\n3. **절대 사용자가 방금 입력한 대사를 그대로 반복하거나 따라하지 마십시오.**\n4. NPC는 자신만의 개성 있는 말투로 새로운 질문이나 반응을 던져 대화를 유도하세요.",
    "custom_sys_inst": "당신은 소설 작가입니다. 아래의 [현재 줄거리]를 인지하고 다음 이야기를 전개하세요. 아래 지침에 따라 **최소 3~5문단 이상의 풍부한 분량**으로 서술하세요.\n"
}


# Streamlit 페이지 설정
st.set_page_config(page_title="AI 소설 엔진 v0.1", page_icon="📖", layout="wide")

st.markdown(
    """
    <style>
    /* 사이드바 너비를 400px로 고정 (기본값은 약 250~300px) */
    [data-testid="stSidebar"] {
        min-width: 400px;
        max-width: 400px;
    }
    /* 탭 간의 간격이나 폰트 크기를 살짝 조정하여 가독성 높임 */
    button[data-baseweb="tab"] {
        font-size: 14px;
        margin-right: 0px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if "settings" not in st.session_state:
    if IS_CLOUD:
        # 클라우드에서는 서버 파일을 무시하고 '정의된 기본값'을 직접 복사해서 사용
        # dict.copy()를 써서 원본 데이터가 오염되지 않게 합니다.
        st.session_state.settings = default_settings.copy()
    else:
        # 로컬일 때만 파일(settings.json)에서 읽어옵니다.
        st.session_state.settings = load_json(SETTINGS_FILE, default_settings)
if "messages" not in st.session_state:
    if IS_CLOUD:
        # 클라우드라면 서버 파일(story_log.json)을 무시하고 무조건 빈 리스트로 시작
        st.session_state.messages = []
    else:
        # 로컬일 때만 파일을 읽어옴
        history_data = load_json(HISTORY_FILE, {"chat_history": []})
        st.session_state.messages = history_data.get("chat_history", [])

#--------------------------------------------------------------------------------------------------
# Gemini 모델 설정
# 1. 시도: Streamlit Secrets (클라우드 환경)
api_key = None
try:
    # get()을 사용하기 전에 st.secrets에 접근 가능한지 먼저 확인합니다.
    if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    # 로컬 환경에서 secrets가 없으면 이 에러를 무시하고 넘어갑니다.
    api_key = None

# 2. 로컬 config.json 파일 확인 (내 컴퓨터 환경)
if not api_key:
    config_data = load_json(CONFIG_FILE, {"api_key": ""})
    api_key = config_data.get('api_key', '')

# 최종적으로 결정된 api_key로 모델 설정
# 1. 실시간으로 현재 사용할 수 있는 키를 결정합니다.
current_key = st.session_state.get("user_api_key")

# 2. 세션에 키가 없다면 로컬 파일(config.json)에서 읽어오기 (로컬 환경 배려)
if not current_key and not IS_CLOUD:
    config_data = load_json(CONFIG_FILE, {"api_key": ""})
    current_key = config_data.get('api_key', '')
    if current_key:
        st.session_state.user_api_key = current_key # 세션에 동기화

# 3. 키 존재 여부에 따른 모델 생성 및 경고 제어
if current_key:
    try:
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel('gemini-2.5-flash') # 모델명 확인 필요
        # ✅ 키가 있으므로 경고창을 띄우지 않습니다.
    except Exception as e:
        st.sidebar.error(f"❌ API 연결 오류: {e}")
        model = None
else:
    # 🔴 키가 없을 때만 사이드바에 경고 노출
    st.sidebar.warning("🔑 API 키를 설정 탭에서 입력해주세요.")
    model = None
#--------------------------------------------------------------------------------------------------

# --- [5. 사이드바 구성] ---
with st.sidebar:
    st.header("🎮 시스템 메뉴")
    tab_info, tab_npc, tab_inv, tab_cmd, tab_set = st.tabs(["👤 정보", "👥 인물", "🎒 가방", "⌨️ 도구", "⚙️ 설정"])

    # 정보 탭
    with tab_info:
        s = st.session_state.settings
        st.info(f"**주인공:** {s['player_setting']['name']}\n\n**상태:** {s['player_setting']['current_status']}")

        st.divider()

        st.subheader("🛠️ API 상태")
        
        # 현재 실제로 모델이 사용 중인 active_api_key를 기준으로 판단합니다.
        if active_api_key:
            if key_source == "user":
                st.success("✅ 개인 API 키 연결됨")
                st.caption("현재 본인의 API 쿼터를 사용 중입니다.")
            elif key_source == "cloud":
                st.info("☁️ 공용 API 키 연결됨")
                st.caption("작가님이 제공한 체험용 쿼터를 사용 중입니다.")
            elif key_source == "local":
                # 클라우드 배포 중인데 local이 뜬다면 config.json이 올라간 것일 수 있습니다.
                if IS_CLOUD:
                    st.warning("⚠️ 서버 설정 키 연결됨")
                    st.caption("서버 내장 설정 파일을 사용 중입니다.")
                else:
                    st.success("🏠 로컬 API 키 연결됨")
            
            st.markdown("[사용량 확인](https://aistudio.google.com/app/plan_free)")
        else:
            st.error("❌ API 키 설정 필요")

        st.divider()
        st.subheader("💾 데이터 관리")
    
        if IS_CLOUD:
            st.info("클라우드 모드: 브라우저 종료 시 내용이 사라지니 꼭 저장하세요!")
    
        # 1. 불러오기 (Upload) - 설정값까지 복구
        uploaded_file = st.file_uploader("소설 파일(.json) 불러오기", type="json")
        
        if uploaded_file is not None:
            if "last_uploaded_file" not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
                try:
                    uploaded_data = json.load(uploaded_file)
    
                    # 1. 소설 기록 복구
                    if "chat_history" in uploaded_data:
                        st.session_state.messages = uploaded_data["chat_history"]
            
                    # 2. 설정값 복구
                    if "settings" in uploaded_data:
                        st.session_state.settings.update(uploaded_data["settings"])
            
                    # 3. 🔥 API 키 복구 (키가 파일에 들어있을 경우)
                    if "api_key" in uploaded_data and uploaded_data["api_key"]:
                        st.session_state.user_api_key = uploaded_data["api_key"]
                        # 로컬 환경이라면 파일(config.json)에도 백업해줍니다.
                        if not IS_CLOUD:
                            save_json(CONFIG_FILE, {"api_key": uploaded_data["api_key"]})
            
                    # 처리 완료 기록 및 리런
                    st.session_state.last_uploaded_file = uploaded_file.name
                    st.session_state.show_load_success = True
                    st.rerun() # 리런하면 상단의 get_model_info()가 새 키를 인식해 모델을 자동 생성합니다.
    
                except Exception as e:
                    st.error(f"파일 불러오기 중 오류 발생: {e}")

        # 2. 내보내기 (Download) - 설정값 포함하여 패킹
        has_messages = len(st.session_state.get("messages", [])) > 0

        # 데이터가 있든 없든 다운로드할 JSON 구조는 미리 준비합니다.
        combined_data = {
            "chat_history": st.session_state.get("messages", []),
            "settings": st.session_state.get("settings", {}),
            "api_key": st.session_state.get("user_api_key", "")  # 🔥 현재 세션의 API 키 추가
        }
        json_string = json.dumps(combined_data, indent=4, ensure_ascii=False)

        # 버튼 출력 (if문을 제거하여 항상 보이게 하되, 데이터가 없으면 비활성화)
        st.download_button(
            label="📥 현재 이야기 & 설정(API키포함) 저장",
            data=json_string,
            file_name="my_novel_full_data.json",
            mime="application/json",
            use_container_width=True,
            disabled=not has_messages  # 🔥 메시지가 없으면 버튼이 클릭되지 않음
        )

        # 사용자 가이드 추가 (선택 사항)
        if not has_messages:
            st.caption("※ 소설 내용이 있어야 저장 버튼이 활성화됩니다.")

                
        st.divider()
        st.markdown("""<div style="text-align: center; padding: 10px; background-color: rgba(100, 100, 100, 0.1); border-radius: 10px;">
            <span style="font-size: 2em;">🐱</span><br><b style="color: #FFD700;">제작자: POTG</b></div>""", unsafe_allow_html=True)

    # NPC 관리 탭
    with tab_npc:
        st.subheader("주변 인물 & 호감도")
        chars = st.session_state.settings.get('characters', {})
        visible_chars = {k: v for k, v in chars.items() if v.get('is_visible', True)}
        if not visible_chars:
            st.caption("발견된 인물이 없습니다.")
        for cid, info in visible_chars.items():
            with st.expander(f"📍 {info['name']}"):
                like = info.get('likability', 0)
                st.write(f"**호감도:** {like}/100")
                st.progress(like / 100)
                st.caption(info.get('description', ''))

    # 인벤토리 탭
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

    # 도구 탭
    with tab_cmd:
        st.subheader("📝 소설 도구")
        st.info("💡 **시스템 명령어 안내**")
        st.code("!추가 인물명", language=None)
        st.caption("입력 시 NPC가 자동 생성됩니다.")
        st.divider()
        
        if st.session_state.messages:
            full_text = "".join([f"[{'주인공' if m['role']=='user' else 'AI 작가'}]\n{m['parts'][0]}\n\n" for m in st.session_state.messages])
            st.download_button("📥 현재 이야기 다운로드(txt)", data=full_text, file_name="story.txt")
        st.divider()
        if st.button("🔄 이야기 초기화"):
            st.session_state.messages = []; save_json(HISTORY_FILE, {"chat_history": []}); st.rerun()

    # 설정 탭
    with tab_set:

        st.subheader("🔑 API 보안/설정")
        
        if IS_CLOUD:
            st.warning("클라우드 모드입니다. 브라우저를 닫으면 내용이 사라지니 하단에서 파일을 꼭 백업하세요!")

        # 1. 표시할 키 결정 로직
        # 우선 세션에 있는지 확인
        display_key = st.session_state.get("user_api_key", "")
    
        # 세션에 없고, 로컬 환경이라면 config.json에서 읽어오기
        if not display_key and not IS_CLOUD:
            config_data = load_json(CONFIG_FILE, {"api_key": ""})
            display_key = config_data.get('api_key', '')
            # 읽어온 키를 세션에도 미리 넣어두면 get_model_info가 바로 인식합니다.
            if display_key:
                st.session_state.user_api_key = display_key

        # 2. 입력 박스 (이제 로컬 키가 있다면 자동으로 채워집니다)
        user_key_input = st.text_input(
            "Gemini API Key", 
            value=display_key, # 여기서 결정된 키를 보여줍니다.
            type="password",
            help="Google AI Studio에서 발급받은 키를 입력하세요."
        )
    

        # 버튼들을 가로로 배치하기 위해 컬럼 생성
        col_key1, col_key2 = st.columns([1, 2])

        with col_key1:
            # 키 적용 및 저장 버튼
            if st.button("✅ 개인 키 적용/저장", use_container_width=True):
                if user_key_input:
                    # 1. 공통: 현재 세션에 즉시 반영
                    st.session_state.user_api_key = user_key_input
                    
                    # 2. 로컬 환경일 때만: config.json 파일에 영구 저장
                    if not IS_CLOUD:
                        try:
                            save_json(CONFIG_FILE, {"api_key": user_key_input})
                            st.success("🏠 로컬 설정 파일에 키가 저장되었습니다!")
                        except:
                            st.error("파일 저장 중 오류가 발생했습니다.")
                    else:
                        st.success("☁️ 클라우드 세션에 키가 적용되었습니다!")
                    
                    # 3. 즉시 반영을 위해 리런 (상단의 get_model 함수가 새 키를 인식함)
                    st.rerun()
                else:
                    st.warning("키를 입력해주세요.")

        with col_key2:
            # Google AI Studio 링크 버튼 유지
            st.link_button("🔑 API keys | Google AI Studio", 
                           "https://aistudio.google.com/app/apikey", 
                           use_container_width=True)

        st.divider()

        # 무료 버전 제한 사항 경고 문구 추가
        st.warning("""
        ⚠️ **무료 API(Free Tier) 사용 주의사항**
        - **분당 호출 제한 (RPM):** 1분당 최대 **15회**만 요청 가능합니다.
        - **분당 토큰 제한 (TPM):** 1분당 **100만 토큰**까지 사용 가능합니다.
        - **일일 제한 (RPD):** 하루 최대 **1,500회** 요청 가능합니다.
        - 너무 빠르게 연속으로 입력하면 '429 Too Many Requests' 오류가 발생할 수 있습니다.
        """, icon="🚫")

        st.divider()

        # 소설 기본 설정
        st.subheader("📖 소설 기본 설정")
        with st.form("basic_set"):
            s = st.session_state.settings
            new_w = st.text_area("세계관", value=s.get('world_setting', ''))
            new_s = st.text_input("문체", value=s.get('writing_style', ''))
            p_n = st.text_input("주인공 이름", value=s['player_setting'].get('name', ''))
            res_d = st.checkbox("주인공 대사 자동 생성 금지", value=s.get('restrict_player_dialogue', True))
            
            if st.form_submit_button("소설 설정 저장"):
                s.update({
                    "world_setting": new_w, 
                    "writing_style": new_s, 
                    "restrict_player_dialogue": res_d
                })
                s['player_setting']['name'] = p_n
    
                # 로컬은 파일 저장, 클라우드는 세션 유지
                save_json(SETTINGS_FILE, s) 
            
                if IS_CLOUD:
                    st.success("설정이 세션에 반영되었습니다! 영구 저장을 원하시면 '정보' 탭에서 파일을 다운로드하세요.")
                else:
                    st.success("소설 설정이 저장되었습니다!")
                st.rerun()
    
        st.divider()

        # 디자인 및 고급 프롬프트 설정
        st.subheader("🎨 디자인 및 프롬프트 제어")
        with st.form("advanced_settings"):
            col1, col2 = st.columns(2)
            new_faded = col1.color_picker("지문 색상", value=s.get("ui_faded_color", "#C8C8C8"))
            new_dialogue = col2.color_picker("대화문 색상", value=s.get("ui_dialogue_color", "#FFFFFF"))
            new_margin = st.slider("대화문 위아래 여백 (px)", 0, 50, s.get("ui_dialogue_margin", 22))
            
            st.divider()
            new_sys_inst = st.text_area("메인 시스템 지침 (Sys_Inst) 수정에 주의하세요!", 
                                       value=s.get("custom_sys_inst", ""), 
                                       height=100)
            new_rules = st.text_area("핵심 규칙 (Rules) 수정에 주의하세요!", 
                                    value=s.get("custom_rules", ""), 
                                    height=150)
            
            if st.form_submit_button("고급 설정 저장"):
                # 1. 현재 세션의 설정값 갱신 (화면에 즉시 반영됨)
                s.update({
                    "ui_faded_color": new_faded,
                    "ui_dialogue_color": new_dialogue,
                    "ui_dialogue_margin": new_margin,
                    "custom_sys_inst": new_sys_inst,
                    "custom_rules": new_rules
                })
                
                # 2. 로컬 환경일 때만 실제 파일(settings.json)에 저장
                save_json(SETTINGS_FILE, s)
                
                # 3. 사용자 안내 및 화면 갱신
                if IS_CLOUD:
                    st.success("🎨 디자인과 프롬프트가 세션에 적용되었습니다!")
                    st.info("💡 주의: 클라우드에서는 브라우저를 닫으면 초기화됩니다. 영구 저장은 '정보' 탭에서 '다운로드' 하세요.")
                else:
                    st.success("고급 설정이 파일에 저장되었습니다!")
                
                st.rerun()

        # NPC 수동 관리
        st.divider()
        st.subheader("👥 NPC 관리")

        with st.expander("➕ 새 NPC 수동 추가"):
            with st.form("manual_npc_add", clear_on_submit=True):
                m_name = st.text_input("이름")
                m_desc = st.text_area("설명")
                if st.form_submit_button("추가"):
                    chars = st.session_state.settings.get('characters', {})
                    new_id = f"npc_{int(re.sub(r'[^0-9]', '', max(chars.keys(), default='npc_0'))) + 1}"
                    st.session_state.settings['characters'][new_id] = {"name": m_name, "description": m_desc, "likability": 0, "is_visible": True}
                    save_json(SETTINGS_FILE, st.session_state.settings)
                    st.rerun()
        
        for cid, info in list(st.session_state.settings['characters'].items()):
            with st.expander(f"⚙️ {info['name']} 수정/삭제"):
                u_name = st.text_input("이름", value=info['name'], key=f"u_n_{cid}")
                u_desc = st.text_area("설명", value=info['description'], key=f"u_d_{cid}")
                u_vis = st.checkbox("인물탭에 표시", value=info.get('is_visible', True), key=f"u_v_{cid}")
                col1, col2 = st.columns(2)
                if col1.button("저장", key=f"u_s_{cid}"):
                    st.session_state.settings['characters'][cid].update({"name": u_name, "description": u_desc, "is_visible": u_vis})
                    save_json(SETTINGS_FILE, st.session_state.settings)
                    st.rerun()
                if col2.button("삭제", key=f"u_r_{cid}"):
                    del st.session_state.settings['characters'][cid]
                    save_json(SETTINGS_FILE, st.session_state.settings)
                    st.rerun()


# --- [6. 메인 화면 출력] ---
st.title("✨ AI 소설")

# 페이징을 위한 상태 초기화 (처음에는 최근 30개만 표시)
if "display_count" not in st.session_state:
    st.session_state.display_count = 30

all_messages = st.session_state.messages
total_msgs = len(all_messages)

# 1. 이전 기록 더보기 버튼
if total_msgs > st.session_state.display_count:
    if st.button("🔼 이전 기록 더보기", use_container_width=True):
        st.session_state.display_count += 30
        st.rerun()

# 2. 현재 보여줄 메시지 범위 계산 (뒤에서부터 display_count 만큼)
start_idx = max(0, total_msgs - st.session_state.display_count)
msgs_to_show = all_messages[start_idx:]

# 3. 메시지 출력
for i, msg in enumerate(msgs_to_show):
    # 실제 전체 리스트에서의 인덱스 계산 (삭제/수정용)
    real_idx = start_idx + i
    
    with st.chat_message(msg["role"]):
        st.markdown(format_novel_text(msg["parts"][0]), unsafe_allow_html=True)
        
        # 삭제 버튼 레이아웃
        c1, c2 = st.columns([11, 1])
        if c2.button("🗑️", key=f"del_{real_idx}"):
            st.session_state.messages.pop(real_idx)
            save_json(HISTORY_FILE, {"chat_history": st.session_state.messages})
            st.rerun()

# --- [7. 채팅 입력 및 AI 응답 처리] ---
if prompt := st.chat_input("행동이나 대사를 입력하세요..."):
    # 명령어 처리 (!추가)
    if model is None:
        st.error("⚠️ API 키가 설정되지 않았습니다! '⚙️ 설정' 탭에서 Gemini API 키를 입력하거나 적용해 주세요.")
    else:

        if prompt.startswith("!추가 "):
            try:
                name_part = prompt.replace("!추가 ", "").strip()
                chars = st.session_state.settings.get('characters', {})
                new_id = f"npc_{int(re.sub(r'[^0-9]', '', max(chars.keys(), default='npc_0'))) + 1}"
                st.session_state.settings['characters'][new_id] = {"name": name_part, "description": "새로 추가된 인물", "likability": 0, "is_visible": True}
                save_json(SETTINGS_FILE, st.session_state.settings)
                st.toast(f"✨ {name_part}가 추가되었습니다!"); st.rerun()
            except: st.error("명령어 형식을 확인하세요.")
        
        # 일반 채팅 처리
        else:
            with st.chat_message("user"):
                st.markdown(format_novel_text(prompt), unsafe_allow_html=True)

            st.session_state.messages.append({"role": "user", "parts": [prompt]})
            save_json(HISTORY_FILE, {"chat_history": st.session_state.messages})

            # 일정 주기마다 요약 업데이트
            if len(st.session_state.messages) % 10 == 0:
                with st.spinner("중간 줄거리 정리 중..."):
                    old_summary = st.session_state.settings.get('story_summary', "")
                    new_summary = get_summary(config_data['api_key'], st.session_state.messages, old_summary)
                    st.session_state.settings['story_summary'] = new_summary
                    save_json(SETTINGS_FILE, st.session_state.settings)
            
            # AI 작가 응답 생성
            with st.chat_message("model"):
                with st.spinner("작가가 집필 중..."):
                    ss = st.session_state.settings
                    p = ss['player_setting']
                    current_story = ss.get('story_summary', "이제 막 이야기가 시작되었습니다.")
                    char_info = "\n".join([f"- {v['name']}: {v['description']} (호감도: {v.get('likability', 0)})" for v in ss['characters'].values() if v.get('is_visible', True)])

                    # 토큰 절약을 위해 전송 기록 최적화
                    history_to_send = st.session_state.messages[-6:]

                    # 시스템 지침 조립
                    restriction_rule = f"1. [절대 금지]: 주인공({p['name']})의 직접적인 대사, 생각, 감정 묘사를 당신(AI)이 임의로 작성하지 마십시오." if ss.get('restrict_player_dialogue', True) else f"1. [허용]: 주인공({p['name']})의 대사를 상황에 맞게 작성하세요."

                    sys_inst = (
                        f"{ss.get('custom_sys_inst', '당신은 소설 작가입니다.')}\n\n"
                        f"[현재 줄거리]: {current_story}\n\n"
                        f"[인물 정보]:\n{char_info}\n\n"
                        f"[제한 사항]:\n{restriction_rule}\n\n"
                        f"[핵심 규칙]:\n{ss.get('custom_rules', '')}\n\n"
                        f"문체: {ss.get('writing_style', '')}\n"
                        f"세계관: {ss.get('world_setting', '').replace('{{user}}', p['name'])}\n"
                    )
                    
                    try:
                        chat = model.start_chat(history=history_to_send[:-1])
                        response = chat.send_message(f"{sys_inst}\n\n입력: {prompt}")
                        st.session_state.messages.append({"role": "model", "parts": [response.text]})
                        save_json(HISTORY_FILE, {"chat_history": st.session_state.messages})
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류: {e}")
