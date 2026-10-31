import streamlit as st
import pandas as pd
from src.analytics import load_frames, campaign_roi, model_summary, funnel_metrics, exception_report, MODELS

st.set_page_config(page_title="YottaFlex Marketing Attribution",layout="wide")
st.title("Marketing Attribution & ROI Analytics")
st.caption("Synthetic, reproducible data • First-touch, last-touch, linear and position-based attribution")
db="data/attribution.db"
try: frames=load_frames(db)
except Exception:
    st.error("Dataset not found. Run `python -m src.generator --scale starter` first.")
    st.stop()

model=st.sidebar.selectbox("Attribution model",MODELS,index=2)
roi=campaign_roi(frames,model)
summary=model_summary(frames)
funnel=funnel_metrics(frames)
exc=exception_report(frames)

c1,c2,c3,c4=st.columns(4)
c1.metric("Contacts",f"{len(frames['Touchpoint']['contact_id'].dropna().unique()):,}")
c2.metric("Touchpoints",f"{len(frames['Touchpoint']):,}")
c3.metric("Opportunities",f"{len(frames['Opportunity']):,}")
c4.metric("Closed won",f"{funnel['closed_won']:,}")

st.subheader("Attribution model comparison")
st.dataframe(summary,use_container_width=True,hide_index=True)
st.bar_chart(summary.set_index("model")["attributed_revenue"])
st.subheader(f"Campaign ROI – {model.replace('_',' ').title()}")
st.dataframe(roi.sort_values("attributed_revenue",ascending=False),use_container_width=True,hide_index=True)
st.download_button("Download campaign ROI CSV",roi.to_csv(index=False),"campaign_roi.csv","text/csv")

st.subheader("Funnel metrics")
st.json(funnel)
st.subheader("Exceptions requiring review")
st.dataframe(pd.DataFrame([{"exception":k,"count":v} for k,v in exc.items()]),use_container_width=True,hide_index=True)
st.info("ROI is calculated only for USD cost records without a labelled issue. Missing or mismatched spend remains visible; it is not silently converted.")
