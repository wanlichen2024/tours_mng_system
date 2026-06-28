import streamlit as st
import requests
import json
from datetime import datetime

# ============================================
# 配置区域
# ============================================
# 优先从 secrets 读取，若没有则使用硬编码（请替换）
try:
    MAKE_WEBHOOK_URL = st.secrets["MAKE_WEBHOOK_URL"]
except:
    MAKE_WEBHOOK_URL = "https://hook.us2.make.com/odw2vopvquxwpgko6pz4xmc38qcrbwps"  # 请替换为你的完整URL

# ============================================
# Streamlit UI
# ============================================
st.set_page_config(page_title="新西兰入境团操作助手", layout="wide")

st.title("🇳🇿 新西兰入境团操作助手")
st.markdown("---")

with st.form("trigger_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        group_id = st.text_input(
            "团队编号 (Group ID)", 
            placeholder="例如: NZ-2026-001",
            help="用于标识该团队的唯一编号"
        )
    
    with col2:
        start_date = st.date_input(
            "出发日期 (Start Date)",
            value=datetime.now().date(),
            help="系列团新西兰段第1天的日期"
        )
    
    with col3:
        pax = st.number_input(
            "团队人数 (PAX)", 
            min_value=1, 
            max_value=100, 
            value=30, 
            step=1,
            help="团队游客总人数"
        )
    
    route_code = st.text_input(
        "路线代码 (可选，留空则AI自动识别)", 
        placeholder="例如: AU-NZ-13D",
        help="如果已知路线代码，填写后可加速匹配"
    )
    
    submitted = st.form_submit_button("🚀 启动自动化流程", type="primary")

# ============================================
# 处理表单提交
# ============================================
if submitted:
    if not group_id:
        st.error("❌ 请填写团队编号")
        st.stop()
    
    payload = {
        "group_id": group_id,
        "start_date": start_date.isoformat(),
        "pax": pax,
        "route_code": route_code if route_code else None
    }
    
    headers = {"Content-Type": "application/json"}
    
    with st.spinner("🔄 正在触发自动化流程，请稍候..."):
        try:
            response = requests.post(
                MAKE_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=60
            )
            
            # 处理响应
            if response.status_code == 200 or response.status_code == 202:
                st.success(f"✅ Webhook 触发成功 (状态码: {response.status_code})")
                
                # 尝试解析 JSON
                try:
                    result = response.json()
                    st.json(result)
                except ValueError:
                    # 如果不是 JSON，显示纯文本
                    text = response.text.strip()
                    if text:
                        st.info(f"📝 服务器返回: {text}")
                    else:
                        st.info("📝 服务器已接受请求，但未返回额外数据。")
            else:
                st.error(f"❌ 请求失败，HTTP状态码: {response.status_code}")
                st.text(response.text)
                
        except requests.exceptions.Timeout:
            st.error("⏰ 请求超时，请稍后重试。")
        except requests.exceptions.ConnectionError:
            st.error("🔌 无法连接到服务器，请检查网络。")
        except Exception as e:
            st.error(f"❌ 发生未知错误: {str(e)}")

st.markdown("---")
st.caption("💡 提示：点击启动后，系统将触发 Make.com 自动化场景。请确保 Webhook URL 配置正确。")