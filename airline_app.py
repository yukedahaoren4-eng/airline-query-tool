from lxml import html
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import streamlit as st

# 全局请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

ultra_base_url = "http://www.xmyzl.com/"
list_base_url = "http://www.xmyzl.com/?mod=jidui&typeid=1&page={}"
total_pages = 12
company_url = []
company_data = {}

def get_plane_info(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        name_tag = soup.select_one(
            'html > body > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > h2'
        )
        if not name_tag:
            return
        company_name = name_tag.get_text(strip=True)
        if company_name not in company_data:
            company_data[company_name] = {}

        tables = soup.find_all("table", border="1")
        if not tables:
            return
        table = tables[-1]
        all_tr = table.find_all("tr", recursive=False)
        total_tr = len(all_tr)

        for idx, tr in enumerate(all_tr):
            if idx == 0 or idx == total_tr - 1:
                continue
            td1 = tr.find("td", align="center")
            if not td1:
                continue
            plane_type = td1.get_text(strip=True)
            if plane_type == "合计" or not plane_type:
                continue
            td_list = tr.find_all("td", recursive=False)
            if len(td_list) < 3:
                continue
            td3 = td_list[2]
            inner_tds = td3.find_all("td")
            reg_list = []
            for td in inner_tds:
                txt = td.get_text().replace("\xa0", "").strip()
                if txt:
                    reg_list.append(txt)
            if reg_list:
                company_data[company_name][plane_type] = reg_list
    except Exception:
        return

def create_csv():
    global company_url, company_data
    company_url.clear()
    company_data.clear()

    # 抓取航司列表页
    for page in range(1, total_pages + 1):
        url = list_base_url.format(page)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            doc = html.fromstring(resp.text)
            li_list = doc.xpath('/html/body/div[3]/div[2]/div[2]/ul/li')
            if not li_list:
                continue
            for li in li_list:
                a_href = li.xpath('./span/a/@href')
                if a_href:
                    single_url = ultra_base_url + a_href[0]
                    company_url.append(single_url)
        except Exception:
            continue
        time.sleep(0.3)

    # 逐个抓取航司详情
    for url in company_url:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            doc = html.fromstring(resp.text)
            name_text = doc.xpath('/html/body/div[2]/div[2]/div[2]/div/h2/text()')
            if not name_text:
                continue
            company_name = name_text[0].strip()
            if company_name not in company_data:
                company_data[company_name] = {}

            border_tables = doc.xpath('//table[@border="1"]')
            try:
                if len(border_tables) == 1:
                    table = border_tables[0]
                else:
                    table = border_tables[1]
                res2 = table.xpath('./tr[position() > 1 and position() < last()]')
                for tr in res2:
                    type_name = tr.xpath("./td[1]/text()")
                    if not type_name:
                        continue
                    type_name = type_name[0].strip()
                    reg = [s.strip() for s in tr.xpath("./td[3]/table/tr/td/text()")
                           if s.strip() and s.strip() != '\xa0']
                    if type_name and reg:
                        company_data[company_name][type_name] = reg
            except IndexError:
                get_plane_info(url)
        except Exception:
            continue
        time.sleep(0.3)

    # 保存文件
    with open("airline_data.json", "w", encoding="utf-8") as f:
        json.dump(company_data, f, ensure_ascii=False, indent=2)
    return len(company_url)

def load_data():
    with open("airline_data.json", "r", encoding="utf-8") as f:
        return json.load(f)

def search_airline_all(airline_name):
    data = load_data()
    if airline_name not in data:
        return f"无此航司：{airline_name}"
    return data[airline_name]

def search_airline_model(airline_name, model_name):
    data = load_data()
    airline_info = data.get(airline_name)
    if not airline_info:
        return f"未找到航司：{airline_name}"
    regs = airline_info.get(model_name)
    if regs is None:
        return f"{airline_name} 无{model_name}机型"
    return regs

def search_reg(reg_num):
    data = load_data()
    result = []
    for airline, model_dict in data.items():
        for model, reg_list in model_dict.items():
            if reg_num in reg_list:
                result.append((airline, model))
    if not result:
        return f"未匹配注册号：{reg_num}"
    return result

# ===================== Streamlit 界面（已改为下拉选择）=====================
st.set_page_config(page_title="民航机队查询工具", layout="wide")
st.title("✈️ 科哥的民航航司机队查询工具")
st.divider()

json_file = "airline_data.json"
airline_list = []
model_list = []

# 如果数据文件存在，预加载航司列表
if os.path.exists(json_file):
    all_data = load_data()
    airline_list = sorted(list(all_data.keys()))

# 数据爬取区域
with st.expander("🔧 数据更新/爬取", expanded=not os.path.exists(json_file)):
    if st.button("开始爬取航司机队数据", type="primary"):
        with st.spinner("正在爬取，请耐心等待..."):
            count = create_csv()
        st.success(f"✅ 完成！共采集 {count} 条航司链接，数据已保存，请刷新页面加载下拉选项")

st.divider()

# 三个功能标签页
tab1, tab2, tab3 = st.tabs(["📋 查询航司全部机队", "✈️ 航司+机型查注册号", "🔍 注册号反向查询"])

# 标签1：航司下拉选框 + 查询全部机队
with tab1:
    st.subheader("选择航司，查询全部机型与注册号(请输入航司全程,例如 中国国际航空)")
    if airline_list:
        selected_airline1 = st.selectbox("请选择航司", options=airline_list)
        if st.button("查询", key="btn1"):
            res = search_airline_all(selected_airline1)
            if isinstance(res, str):
                st.error(res)
            else:
                st.success(f"【{selected_airline1}】机队信息")
                for model, regs in res.items():
                    st.markdown(f"**{model}**：{' '.join(regs)}")
    else:
        st.info("请先爬取数据，生成航司列表")

# 标签2：航司下拉 + 对应机型下拉
with tab2:
    st.subheader("选择航司 + 机型，精准查询注册号")
    if airline_list:
        col1, col2 = st.columns(2)
        with col1:
            selected_airline2 = st.selectbox("请选择航司", options=airline_list, key="air2")
        # 根据选中航司，动态加载对应机型
        all_data = load_data()
        current_models = sorted(list(all_data[selected_airline2].keys()))
        with col2:
            selected_model = st.selectbox("请选择机型", options=current_models)

        if st.button("查询", key="btn2"):
            res = search_airline_model(selected_airline2, selected_model)
            if isinstance(res, str):
                st.error(res)
            else:
                st.success(f"注册号列表")
                st.markdown(" ".join(res))
    else:
        st.info("请先爬取数据，生成航司列表")

# 标签3：注册号反向查询（保留输入框）
with tab3:
    st.subheader("输入注册号，反向查航司&机型(注册号无需输入B)")
    reg_input = st.text_input("输入飞机注册号", placeholder="例如：1083")
    if st.button("查询", key="btn3"):
        if not os.path.exists(json_file):
            st.error("请先执行【数据爬取】")
        elif not reg_input.strip():
            st.warning("请输入注册号")
        else:
            res = search_reg(reg_input.strip())
            if isinstance(res, str):
                st.error(res)
            else:
                st.success("查询结果")
                for airline, model in res:
                    st.markdown(f"注册号 **{reg_input}** → 航司：{airline} | 机型：{model}")