import streamlit as st

st.set_page_config(page_title="CNG Demand Planner", layout="wide")
st.title("CNG Demand Planner - PS000002")
st.caption("Station-level demand forecasting and network expansion support for Gujarat Gas")

tab1, tab2, tab3, tab4 = st.tabs(["Network map", "Forecast", "Spacing analysis", "Ranked sites"])
with tab1:
    st.info("TODO: map of real stations (data/raw/osm_cng_stations_gujarat.csv)")
with tab2:
    st.info("TODO: actual vs forecast, baseline vs model error")
with tab3:
    st.info("TODO: cannibalisation / overlap vs distance, recommended spacing")
with tab4:
    st.info("TODO: ranked candidate sites with EV scenario slider")
