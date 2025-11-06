import time
import streamlit as st
import pyrebase
import firebase_admin
import requests
from firebase_admin import credentials, firestore
from firebase_admin import auth as admin_auth
from collections import deque
from datetime import datetime, timezone
from ollama import Client
from streamlit_extras.stylable_container import stylable_container

st.set_page_config(page_title="Chat + Firebase", page_icon="💬")
MODEL = "llama3.2:1b"
client = Client(
    host='http://dejix-34-132-26-43.a.free.pinggy.link'
)

def ollama_stream(history_messages: list[dict]):
    """
    Stream tokens from Ollama /api/chat. Yields string chunks suitable for st.write_stream.
    """
    print(history_messages)
    response = client.chat(
        model=MODEL,
        messages=history_messages
    )
    return response['message']['content']

def ollama_generate_itinerary(prompt: str):
    """
    Gửi một prompt tạo lịch trình đến Ollama và trả về kết quả.
    Sử dụng logic tương tự như ollama_stream nhưng chỉ với 1 prompt.
    """
    response = client.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response['message']['content']

def save_message(uid: str, role: str, content: str):
    doc = {
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc)
    }
    db.collection("chats").document(uid).collection("messages").add(doc)

def load_last_messages(uid: str, limit: int = 8):
    q = (db.collection("chats").document(uid)
        .collection("messages")
        .order_by("ts", direction=firestore.Query.DESCENDING)
        .limit(limit))
    docs = list(q.stream())
    docs.reverse()
    out = []
    for d in docs:
        data = d.to_dict()
        out.append({"role": data.get("role", "assistant"),
                    "content": data.get("content", "")})
    return out

params = st.query_params
raw_token = params.get("id_token")
if isinstance(raw_token, list):
    id_token = raw_token[0]
else:
    id_token = raw_token
    
if id_token and not st.session_state.get("user"):
    id_token = params["id_token"][0]
    try:
        decoded = admin_auth.verify_id_token(id_token)
        st.session_state.user = {
            "email": decoded.get("email"),
            "uid": decoded.get("uid"),
            "idToken": id_token,
        }
        msgs = []
        try:
            msgs = load_last_messages(st.session_state.user["uid"], limit=8)
        except Exception:
            pass
        st.session_state.messages = deque(
            msgs if msgs else [{"role": "assistant", "content": "Xin chào Xin chào 👋! Tôi là Mika. Tôi có thể giúp gì cho bạn?"}],
            maxlen=8
        )
        st.experimental_set_query_params()
        st.success("Đăng nhập Google thành công!")
        st.rerun()
    except Exception as e:
        st.error(f"Xác thực Google thất bại: {e}")


@st.cache_resource
def get_firebase_clients():
    # Pyrebase (Auth)
    firebase_cfg = st.secrets["firebase_client"]
    firebase_app = pyrebase.initialize_app(firebase_cfg)
    auth = firebase_app.auth()

    # Admin (Firestore)
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase_admin"]))
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    return auth, db

auth, db = get_firebase_clients()


if "user" not in st.session_state:
    st.session_state.user = None 

if "messages" not in st.session_state:
    st.session_state.messages = deque([
        {"role": "assistant", "content": "Xin chào Xin chào 👋! Tôi là Mika. Tôi có thể giúp gì cho bạn?"}
    ], maxlen=8)
else:
    if not isinstance(st.session_state.messages, deque):
        st.session_state.messages = deque(st.session_state.messages[-8:], maxlen=8)

if "chat_open" not in st.session_state:
    st.session_state.chat_open = False

def login_form():
    st.markdown("<h3 style='text-align: center;'>Đăng nhập</h3>", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", key="email_login")
        password = st.text_input("Mật khẩu", type="password", key="password_login")
        col1, _, col2 = st.columns([0.75, 0.75, 0.75])
        with col1:
            with stylable_container(
                "black",
                css_styles="""
                button {
                    background-color: #0DDEAA;
                    color: black;
                }""",
            ):
                login = st.form_submit_button("Đăng nhập")
        with col2:
            goto_signup = st.form_submit_button("Chưa có tài khoản? Đăng ký", type="primary")

    if goto_signup:
        st.session_state["show_signup"] = True
        st.session_state["show_login"] = False
        st.rerun()

    if login:
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            # user: dict có idToken, refreshToken, localId (uid), email
            st.session_state.user = {
                "email": email,
                "uid": user["localId"],
                "idToken": user["idToken"]
            }
            # tải lịch sử gần nhất từ Firestore
            msgs = load_last_messages(st.session_state.user["uid"], limit=8)
            if msgs:
                st.session_state.messages = deque(msgs, maxlen=8)
            else:
                st.session_state.messages = deque([
                    {"role": "assistant", "content": "Xin chào Xin chào 👋! Tôi là Mika. Tôi có thể giúp gì cho bạn?"}
                ], maxlen=8)
            st.success("Đăng nhập thành công!")
            st.rerun()
        except Exception as e:
            st.error(f"Đăng nhập thất bại: {e}")

def signup_form():
    st.subheader("Đăng ký")
    with st.form("signup_form", clear_on_submit=False):
        email = st.text_input("Email", key="email_signup")
        password = st.text_input("Mật khẩu (≥6 ký tự)", type="password", key="password_signup")
        col1, _, col2 = st.columns([0.75, 0.75, 0.75])
        with col1:
            with stylable_container(
                "black-1",
                css_styles="""
                button {
                    background-color: #0DD0DE;
                    color: black;
                }""",
            ):
                signup = st.form_submit_button("Tạo tài khoản")
        with col2:
                goto_login = st.form_submit_button("Đã có tài khoản? Đăng nhập", type="primary")

    if goto_login:
        st.session_state["show_signup"] = False
        st.session_state["show_login"] = True
        st.rerun()

    if signup:
        try:
            user = auth.create_user_with_email_and_password(email, password)
            st.success("Tạo tài khoản thành công! Vui lòng đăng nhập.")
            time.sleep(3)
            st.session_state["show_signup"] = False
            st.session_state["show_login"] = True
            st.rerun()
        except Exception as e:
            st.error(f"Đăng ký thất bại: {e}")

@st.dialog("Trợ lý Mika")
def chat_dialog():
    if not st.session_state.user:
        st.info("Bạn cần đăng nhập để chat và lưu lịch sử.")
        return
    
    chat_body = st.container(height=600, border=True)

    def render_history():
        chat_body.empty()
        with chat_body:
            for msg in list(st.session_state.messages):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
    render_history()

    user_input = st.chat_input("Nhập tin nhắn...", key="dialog_input")
        
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with chat_body:
            with st.chat_message("user"):
                st.markdown(user_input)
        save_message(st.session_state.user["uid"], "user", user_input)
        try:
            reply = ollama_stream(st.session_state.messages)
        except requests.RequestException as e:
            st.error(f"Ollama request failed: {e}")
            reply = ""
        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_message(st.session_state.user["uid"], "assistant", reply)
        st.session_state.chat_open = True
        st.rerun()

st.markdown("<h1 style='text-align: center;'>Streamlit Chat + Firebase Login</h1>", unsafe_allow_html=True)

if "show_signup" not in st.session_state:
    st.session_state["show_signup"] = False
if "show_login" not in st.session_state:
    st.session_state["show_login"] = True

if st.session_state.user:
    st.success(f"Đang đăng nhập: {st.session_state.user['email']}")
    _, col2, _ = st.columns([1.3, 0.75, 1])
    with col2:
        if st.button("Đăng xuất", type="primary"):
            st.session_state.user = None
            st.session_state.chat_open = False
            st.rerun()

# --- Bắt đầu: Phần thêm mới cho Lịch trình Du lịch ---

# Chỉ hiển thị giao diện tạo lịch trình khi người dùng đã đăng nhập
if st.session_state.user:
    st.markdown("## ✈️ Tạo Lịch Trình Du Lịch")

    with st.form("travel_form"):
        # 1. Thành phố xuất phát & Điểm đến
        col_city_1, col_city_2 = st.columns(2)
        with col_city_1:
            origin_city = st.text_input("Thành phố Xuất phát (Origin City)", value="Hà Nội")
        with col_city_2:
            destination_city = st.text_input("Thành phố Điểm đến (Destination City)", value="Đà Nẵng")

        # 2. Ngày tháng
        col_date_1, col_date_2 = st.columns(2)
        with col_date_1:
            start_date = st.date_input("Ngày Bắt đầu", datetime.now().date())
        with col_date_2:
            # Ngày kết thúc phải sau ngày bắt đầu
            end_date = st.date_input("Ngày Kết thúc", datetime.now().date())

        # 3. Sở thích và Tốc độ
        col_interest, col_pace = st.columns(2)
        with col_interest:
            interests = st.multiselect(
                "Sở thích (Interests)",
                ['food', 'museums', 'nature', 'nightlife'],
                default=['food', 'nature'],
                placeholder="Chọn ít nhất một sở thích"
            )
        with col_pace:
            pace = st.radio(
                "Tốc độ (Pace)",
                ['relaxed', 'normal', 'tight'],
                index=1,
                horizontal=True
            )
               
        # Nút tạo lịch trình
        submit_button = st.form_submit_button("Lên Lịch Trình! 🗺️", type="primary")

# ... (ở cuối khối st.form("travel_form")) ...

        if submit_button:
            if not origin_city or not destination_city or not interests:
                st.error("Vui lòng nhập đầy đủ Thành phố Xuất phát, Điểm đến và Sở thích.")
            elif start_date > end_date:
                st.error("Ngày Kết thúc phải sau Ngày Bắt đầu.")
            else:
                # 1. Xây dựng Prompt
                duration = (end_date - start_date).days + 1

                prompt_template = f"""
                Bạn là một trợ lý du lịch chuyên nghiệp. Hãy tạo một lịch trình du lịch {duration} ngày
                cho chuyến đi từ {origin_city} đến {destination_city}.

                Thông tin chi tiết:
                - **Ngày đi:** Từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}
                - **Sở thích chính:** {', '.join(interests)}
                - **Tốc độ:** {pace}

                Lịch trình phải được trình bày theo định dạng từng ngày, bao gồm các hoạt động/địa điểm cho buổi **Sáng**, **Chiều**, và **Tối**, kèm theo **giải thích ngắn gọn** tại sao nên chọn hoạt động đó. Lịch trình phải bằng tiếng Việt.
                """

                # 2. Gọi LLM
                with st.spinner('Đang tạo lịch trình chi tiết...'):
                    try:
                        itinerary = ollama_generate_itinerary(prompt_template)
                        st.session_state.itinerary_output = itinerary
                    except requests.RequestException as e:
                        st.error(f"Lỗi kết nối với Ollama: {e}. Vui lòng kiểm tra máy chủ LLM.")
                        st.session_state.itinerary_output = None

                # Tải lại giao diện để hiển thị kết quả
                st.rerun()

    # --- Kết thúc: Phần nhập liệu Du lịch ---
    
    # Khu vực hiển thị lịch trình
    if "itinerary_output" not in st.session_state:
        st.session_state.itinerary_output = None
        
    st.divider()
    
    if st.session_state.itinerary_output:
        st.markdown("### Lịch Trình Du Lịch Đề Xuất")
        st.info(st.session_state.itinerary_output)
    elif submit_button:
        st.warning("Đang tạo lịch trình... Vui lòng chờ.")
else:
    if st.session_state.get("show_signup", False):
        signup_form()
    elif st.session_state.get("show_login", True):
        login_form()

st.divider()
st.markdown("<h5 style='text-align: center;'>Click 💬 để mở hộp thoại chat</h5>", unsafe_allow_html=True)

st.markdown('<div id="fab-anchor"></div>', unsafe_allow_html=True)
with stylable_container(
                "black-3",
                css_styles="""
                button {
                    background-color: #66c334;
                    color: black;
                    width: 704px !important; 
                    height: 30px; 
                }""",
            ):
    fab_clicked = st.button("💬", key="open_chat_fab", help="Mở chat")
    
if fab_clicked:
    st.session_state.chat_open = True
    st.rerun()

if st.session_state.chat_open:
    chat_dialog()


st.markdown("""
<style>
#fab-anchor + div button {
    position: fixed;
    bottom: 16px;
    right: 16px;
    width: 120px !important; 
    height: 60px; 
    border-radius: 50%;
    font-size: 26px; 
    line-height: 1; 
    padding: 0;
    box-shadow: 0 6px 18px rgba(0,0,0,0.25);
    z-index: 10000;
}
#fab-anchor + div button:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 24px rgba(250,206,175,0.28);
}
</style>
""", unsafe_allow_html=True)
