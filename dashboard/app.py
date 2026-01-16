"""
Streamlit Dashboard - YouTube Content Assistant
รัน: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# เพิ่ม project root ใน path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Import modules
from src.db.connection import init_db, session_scope
from src.db.repository import (
    VideoRepository,
    DailyMetricRepository,
    ResearchItemRepository,
    ContentIdeaRepository,
    PlaybookRuleRepository,
    RunLogRepository,
)
from src.db.models import Video, DailyMetric
from src.modules.analytics import AnalyticsModule
from src.modules.content import ContentModule
from src.modules.research import ResearchModule
from src.modules.playbook import PlaybookModule
from src.utils.config import load_config

# Page config
st.set_page_config(
    page_title="YouTube Content Assistant",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF0000;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .success-text { color: #28a745; }
    .warning-text { color: #ffc107; }
    .danger-text { color: #dc3545; }
    .info-box {
        background-color: #e7f3ff;
        border-left: 4px solid #2196F3;
        padding: 1rem;
        margin: 1rem 0;
    }
    .youtube-red { color: #FF0000; }
    .chart-container {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state"""
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    if "db_initialized" not in st.session_state:
        init_db(st.session_state.config.database.path)
        st.session_state.db_initialized = True


def render_sidebar():
    """Render sidebar navigation"""
    st.sidebar.markdown("# 🎬 YouTube Assistant")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "เมนู",
        [
            "🏠 หน้าหลัก",
            "📊 YouTube Analytics",
            "📈 Performance Trends",
            "💡 Content Ideas",
            "🔬 Research",
            "📖 Playbook",
            "📜 Run Logs",
            "⚙️ Settings",
        ],
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 สถานะระบบ")
    st.sidebar.markdown(f"**วันที่:** {datetime.now().strftime('%d/%m/%Y')}")
    st.sidebar.markdown(f"**เวลา:** {datetime.now().strftime('%H:%M:%S')}")
    
    return page


def render_home_page():
    """Render home page with overview"""
    st.markdown('<p class="main-header">🎬 YouTube Content Assistant</p>', unsafe_allow_html=True)
    st.markdown("ระบบผู้ช่วยสร้างเนื้อหา YouTube ที่ปรับปรุงตัวเองได้")
    
    st.markdown("---")
    
    with session_scope() as session:
        video_repo = VideoRepository(session)
        metric_repo = DailyMetricRepository(session)
        idea_repo = ContentIdeaRepository(session)
        research_repo = ResearchItemRepository(session)
        rule_repo = PlaybookRuleRepository(session)
        run_repo = RunLogRepository(session)
        
        # Overview metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_videos = video_repo.count()
            st.metric("📹 วิดีโอทั้งหมด", total_videos)
        
        with col2:
            total_metrics = metric_repo.count()
            st.metric("📊 Daily Metrics", f"{total_metrics:,}")
        
        with col3:
            total_ideas = idea_repo.count()
            st.metric("💡 ไอเดียทั้งหมด", total_ideas)
        
        with col4:
            total_research = research_repo.count()
            st.metric("🔬 Research Items", total_research)
        
        with col5:
            total_rules = rule_repo.count()
            st.metric("📖 Playbook Rules", total_rules)
        
        st.markdown("---")
        
        # Recent activity
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 วิดีโอล่าสุด")
            recent_videos = video_repo.get_recent(days=30, limit=5)
            if recent_videos:
                for video in recent_videos:
                    with st.container():
                        title = video.title[:50] + "..." if len(video.title) > 50 else video.title
                        st.markdown(f"**{title}**")
                        st.caption(f"Views: {video.view_count:,} | Likes: {video.like_count:,}")
            else:
                st.info("ยังไม่มีวิดีโอ - รัน `python scripts/fetch_youtube.py --videos` เพื่อดึงข้อมูล")
        
        with col2:
            st.subheader("💡 ไอเดียล่าสุด")
            recent_ideas = idea_repo.get_by_status("draft", limit=5)
            if recent_ideas:
                for idea in recent_ideas:
                    with st.container():
                        priority_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                        title = idea.title[:50] + "..." if len(idea.title) > 50 else idea.title
                        st.markdown(f"{priority_color.get(idea.priority, '⚪')} **{title}**")
                        st.caption(f"Category: {idea.category} | Score: {idea.potential_score:.0f}")
            else:
                st.info("ยังไม่มีไอเดีย")
        
        st.markdown("---")
        
        # Recent runs
        st.subheader("📜 การทำงานล่าสุด")
        recent_runs = run_repo.get_recent_runs(limit=5)
        if recent_runs:
            run_data = []
            for run in recent_runs:
                run_data.append({
                    "Run ID": run.run_id[:20] + "...",
                    "Type": run.run_type,
                    "Status": "✅" if run.status == "completed" else "❌",
                    "Started": run.started_at.strftime("%d/%m %H:%M"),
                    "Duration": f"{run.duration_seconds:.1f}s" if run.duration_seconds else "-",
                })
            st.dataframe(pd.DataFrame(run_data), use_container_width=True)
        else:
            st.info("ยังไม่มีประวัติการทำงาน")


def render_youtube_analytics_page():
    """Render YouTube Analytics page with CTR, views, avgViewDuration"""
    st.header("📊 YouTube Analytics Dashboard")
    
    with session_scope() as session:
        video_repo = VideoRepository(session)
        metric_repo = DailyMetricRepository(session)
        
        # ตรวจสอบว่ามีข้อมูลหรือไม่
        total_videos = video_repo.count()
        total_metrics = metric_repo.count()
        
        if total_videos == 0:
            st.warning("⚠️ ยังไม่มีข้อมูลวิดีโอ")
            st.info("""
            **วิธีดึงข้อมูล:**
            1. ตั้งค่า OAuth: `python scripts/validate_youtube_auth.py --authenticate`
            2. ดึงข้อมูลวิดีโอ: `python scripts/fetch_youtube.py --all`
            """)
            return
        
        # Date range selector
        st.subheader("📅 เลือกช่วงเวลา")
        col1, col2 = st.columns(2)
        with col1:
            days_back = st.selectbox(
                "ช่วงเวลา",
                [7, 14, 30, 60, 90],
                index=2,
                format_func=lambda x: f"{x} วันล่าสุด"
            )
        
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=days_back - 1)
        
        with col2:
            st.info(f"📆 {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")
        
        st.markdown("---")
        
        # ดึงข้อมูล metrics
        metrics = metric_repo.get_metrics_in_range(start_date, end_date)
        
        if not metrics:
            st.warning("⚠️ ยังไม่มีข้อมูล metrics ในช่วงเวลานี้")
            st.info("รัน `python scripts/fetch_youtube.py --metrics` เพื่อดึงข้อมูล")
            return
        
        # สร้าง DataFrame
        # ใช้ getattr เพื่อรองรับกรณี column ไม่มีอยู่ (ก่อน migration)
        metrics_df = pd.DataFrame([{
            "date": m.date,
            "video_id": m.video_id,
            "views": m.views or 0,
            "watch_time_minutes": m.watch_time_minutes or 0,
            "average_view_duration": m.average_view_duration or 0,
            "average_view_percentage": m.average_view_percentage or 0,
            "likes": m.likes or 0,
            "comments": m.comments or 0,
            "shares": m.shares or 0,
            "subscribers_gained": m.subscribers_gained or 0,
            "impressions": getattr(m, 'impressions', None) or 0,
            "impressions_ctr": getattr(m, 'impressions_ctr', None) or 0,
        } for m in metrics])
        
        # Summary metrics
        st.subheader("📈 สรุปภาพรวม")
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        total_views = metrics_df["views"].sum()
        total_watch_time = metrics_df["watch_time_minutes"].sum()
        avg_view_duration = metrics_df["average_view_duration"].mean()
        total_subs_gained = metrics_df["subscribers_gained"].sum()
        total_impressions = metrics_df["impressions"].sum()
        avg_ctr = metrics_df["impressions_ctr"].mean() if metrics_df["impressions_ctr"].sum() > 0 else 0
        
        with col1:
            st.metric(
                "👁️ Total Views",
                f"{total_views:,}",
                delta=f"{total_views / days_back:.0f}/วัน"
            )
        
        with col2:
            hours = total_watch_time / 60
            st.metric(
                "⏱️ Watch Time",
                f"{hours:,.1f} ชม.",
                delta=f"{hours / days_back:.1f} ชม./วัน"
            )
        
        with col3:
            st.metric(
                "📊 Avg View Duration",
                f"{avg_view_duration:.1f} วินาที",
            )
        
        with col4:
            st.metric(
                "👥 Subscribers Gained",
                f"+{total_subs_gained:,}",
            )
        
        with col5:
            st.metric(
                "👁️ Impressions",
                f"{total_impressions:,}" if total_impressions > 0 else "-",
            )
        
        with col6:
            st.metric(
                "🎯 Avg CTR",
                f"{avg_ctr:.2f}%" if avg_ctr > 0 else "-",
            )
        
        st.markdown("---")
        
        # Top Videos by different metrics
        st.subheader("🏆 Top Videos")
        
        # ดึงข้อมูลวิดีโอ
        videos = video_repo.get_all(limit=1000)
        video_dict = {v.id: v for v in videos}
        
        # Aggregate by video
        video_metrics = metrics_df.groupby("video_id").agg({
            "views": "sum",
            "watch_time_minutes": "sum",
            "average_view_duration": "mean",
            "average_view_percentage": "mean",
            "likes": "sum",
            "comments": "sum",
            "impressions": "sum",
            "impressions_ctr": "mean",
        }).reset_index()
        
        # เพิ่มชื่อวิดีโอ
        video_metrics["title"] = video_metrics["video_id"].apply(
            lambda x: video_dict.get(x, Video()).title if x in video_dict else "Unknown"
        )
        
        # เพิ่มข้อมูล duration ของวิดีโอ
        video_metrics["duration_seconds"] = video_metrics["video_id"].apply(
            lambda x: video_dict.get(x, Video()).duration_seconds or 0 if x in video_dict else 0
        )
        
        # Tabs for different rankings
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "👁️ Top by Views",
            "📊 Top by CTR",
            "🎥 Top Long Videos by CTR",
            "⏱️ Top by Avg Duration",
            "💬 Top by Engagement"
        ])
        
        with tab1:
            top_views = video_metrics.nlargest(10, "views")[["title", "views", "likes", "comments"]]
            top_views.columns = ["วิดีโอ", "Views", "Likes", "Comments"]
            top_views["วิดีโอ"] = top_views["วิดีโอ"].apply(lambda x: x[:50] + "..." if len(str(x)) > 50 else x)
            st.dataframe(top_views, use_container_width=True, hide_index=True)
        
        with tab2:
            # CTR = impressions_ctr (ถ้ามี) หรือคำนวณจาก views/impressions
            video_metrics["ctr"] = video_metrics.apply(
                lambda row: row["impressions_ctr"] if row["impressions_ctr"] > 0 
                else (row["views"] / row["impressions"] * 100 if row["impressions"] > 0 else 0),
                axis=1
            )
            top_ctr = video_metrics.nlargest(10, "ctr")[["title", "ctr", "impressions", "views"]]
            top_ctr.columns = ["วิดีโอ", "CTR (%)", "Impressions", "Views"]
            top_ctr["วิดีโอ"] = top_ctr["วิดีโอ"].apply(lambda x: x[:50] + "..." if len(str(x)) > 50 else x)
            top_ctr["CTR (%)"] = top_ctr["CTR (%)"].apply(lambda x: f"{x:.2f}%" if x > 0 else "-")
            st.dataframe(top_ctr, use_container_width=True, hide_index=True)
        
        with tab3:
            # Top Long Videos by CTR (เฉพาะวิดีโอยาว > 60 วินาที)
            st.caption("🎥 วิดีโอยาว (Long-form) ที่มี CTR สูงสุด (ความยาว > 60 วินาที)")
            
            # กรองเฉพาะ Long videos (> 60 วินาที)
            long_videos = video_metrics[video_metrics["duration_seconds"] > 60].copy()
            
            if len(long_videos) > 0:
                long_videos["ctr"] = long_videos.apply(
                    lambda row: row["impressions_ctr"] if row["impressions_ctr"] > 0 
                    else (row["views"] / row["impressions"] * 100 if row["impressions"] > 0 else 0),
                    axis=1
                )
                
                # กรองเฉพาะวิดีโอที่มี impressions (มีข้อมูล CTR)
                long_videos_with_ctr = long_videos[long_videos["impressions"] > 0]
                
                if len(long_videos_with_ctr) > 0:
                    top_long_ctr = long_videos_with_ctr.nlargest(10, "ctr")[
                        ["title", "ctr", "impressions", "views", "duration_seconds"]
                    ].copy()
                    top_long_ctr["duration_min"] = top_long_ctr["duration_seconds"].apply(lambda x: f"{x//60}:{x%60:02d}")
                    top_long_ctr = top_long_ctr[["title", "ctr", "impressions", "views", "duration_min"]]
                    top_long_ctr.columns = ["วิดีโอ", "CTR (%)", "Impressions", "Views", "ความยาว"]
                    top_long_ctr["วิดีโอ"] = top_long_ctr["วิดีโอ"].apply(lambda x: x[:50] + "..." if len(str(x)) > 50 else x)
                    top_long_ctr["CTR (%)"] = top_long_ctr["CTR (%)"].apply(lambda x: f"{x:.2f}%" if x > 0 else "-")
                    st.dataframe(top_long_ctr, use_container_width=True, hide_index=True)
                else:
                    st.info("ยังไม่มีข้อมูล Impressions/CTR สำหรับวิดีโอยาว")
            else:
                st.info("ไม่พบวิดีโอยาว (> 60 วินาที) ในช่วงเวลานี้")
        
        with tab4:
            top_duration = video_metrics.nlargest(10, "average_view_duration")[
                ["title", "average_view_duration", "average_view_percentage", "views"]
            ]
            top_duration.columns = ["วิดีโอ", "Avg Duration (s)", "Avg View %", "Views"]
            top_duration["วิดีโอ"] = top_duration["วิดีโอ"].apply(lambda x: x[:50] + "..." if len(str(x)) > 50 else x)
            top_duration["Avg Duration (s)"] = top_duration["Avg Duration (s)"].apply(lambda x: f"{x:.1f}")
            top_duration["Avg View %"] = top_duration["Avg View %"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(top_duration, use_container_width=True, hide_index=True)
        
        with tab5:
            video_metrics["engagement"] = video_metrics["likes"] + video_metrics["comments"]
            top_engagement = video_metrics.nlargest(10, "engagement")[
                ["title", "engagement", "likes", "comments", "views"]
            ]
            top_engagement.columns = ["วิดีโอ", "Total Engagement", "Likes", "Comments", "Views"]
            top_engagement["วิดีโอ"] = top_engagement["วิดีโอ"].apply(lambda x: x[:50] + "..." if len(str(x)) > 50 else x)
            st.dataframe(top_engagement, use_container_width=True, hide_index=True)


def render_trends_page():
    """Render Performance Trends page with charts"""
    st.header("📈 Performance Trends")
    
    with session_scope() as session:
        video_repo = VideoRepository(session)
        metric_repo = DailyMetricRepository(session)
        
        # ตรวจสอบว่ามีข้อมูลหรือไม่
        total_metrics = metric_repo.count()
        
        if total_metrics == 0:
            st.warning("⚠️ ยังไม่มีข้อมูล metrics")
            st.info("รัน `python scripts/fetch_youtube.py --metrics` เพื่อดึงข้อมูล")
            return
        
        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            days_back = st.selectbox(
                "ช่วงเวลา",
                [7, 14, 30, 60, 90],
                index=2,
                format_func=lambda x: f"{x} วันล่าสุด",
                key="trends_days"
            )
        
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=days_back - 1)
        
        # ดึงข้อมูล metrics
        metrics = metric_repo.get_metrics_in_range(start_date, end_date)
        
        if not metrics:
            st.warning("⚠️ ไม่มีข้อมูลในช่วงเวลานี้")
            return
        
        # สร้าง DataFrame
        metrics_df = pd.DataFrame([{
            "date": m.date,
            "views": m.views or 0,
            "watch_time_minutes": m.watch_time_minutes or 0,
            "average_view_duration": m.average_view_duration or 0,
            "likes": m.likes or 0,
            "comments": m.comments or 0,
            "subscribers_gained": m.subscribers_gained or 0,
        } for m in metrics])
        
        # Aggregate by date
        daily_metrics = metrics_df.groupby("date").agg({
            "views": "sum",
            "watch_time_minutes": "sum",
            "average_view_duration": "mean",
            "likes": "sum",
            "comments": "sum",
            "subscribers_gained": "sum",
        }).reset_index()
        
        daily_metrics["date"] = pd.to_datetime(daily_metrics["date"])
        daily_metrics = daily_metrics.sort_values("date")
        
        st.markdown("---")
        
        # Metric selector
        metric_options = {
            "views": "👁️ Views",
            "watch_time_minutes": "⏱️ Watch Time (นาที)",
            "average_view_duration": "📊 Avg View Duration (วินาที)",
            "likes": "👍 Likes",
            "comments": "💬 Comments",
            "subscribers_gained": "👥 Subscribers Gained",
        }
        
        selected_metrics = st.multiselect(
            "เลือก Metrics ที่ต้องการแสดง",
            list(metric_options.keys()),
            default=["views", "watch_time_minutes"],
            format_func=lambda x: metric_options[x]
        )
        
        if not selected_metrics:
            st.warning("กรุณาเลือกอย่างน้อย 1 metric")
            return
        
        # สร้าง charts
        st.subheader("📊 Trend Charts")
        
        for metric in selected_metrics:
            st.markdown(f"### {metric_options[metric]}")
            
            fig, ax = plt.subplots(figsize=(12, 4))
            
            ax.plot(
                daily_metrics["date"],
                daily_metrics[metric],
                color="#FF0000",
                linewidth=2,
                marker="o",
                markersize=4,
            )
            
            ax.fill_between(
                daily_metrics["date"],
                daily_metrics[metric],
                alpha=0.3,
                color="#FF0000",
            )
            
            ax.set_xlabel("วันที่", fontsize=10)
            ax.set_ylabel(metric_options[metric], fontsize=10)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days_back // 10)))
            plt.xticks(rotation=45)
            ax.grid(True, alpha=0.3)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
            
            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total", f"{daily_metrics[metric].sum():,.0f}")
            with col2:
                st.metric("Average", f"{daily_metrics[metric].mean():,.1f}")
            with col3:
                st.metric("Max", f"{daily_metrics[metric].max():,.0f}")
            with col4:
                st.metric("Min", f"{daily_metrics[metric].min():,.0f}")
            
            st.markdown("---")
        
        # Comparison chart
        if len(selected_metrics) >= 2:
            st.subheader("📈 Metrics Comparison (Normalized)")
            
            fig, ax = plt.subplots(figsize=(12, 5))
            
            colors = ["#FF0000", "#282828", "#AAAAAA", "#FF6B6B", "#4ECDC4", "#45B7D1"]
            
            for i, metric in enumerate(selected_metrics):
                # Normalize to 0-100
                values = daily_metrics[metric]
                normalized = (values - values.min()) / (values.max() - values.min()) * 100 if values.max() != values.min() else values
                
                ax.plot(
                    daily_metrics["date"],
                    normalized,
                    color=colors[i % len(colors)],
                    linewidth=2,
                    label=metric_options[metric],
                )
            
            ax.set_xlabel("วันที่", fontsize=10)
            ax.set_ylabel("Normalized Value (0-100)", fontsize=10)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days_back // 10)))
            plt.xticks(rotation=45)
            ax.legend(loc="upper left")
            ax.grid(True, alpha=0.3)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()


def render_content_page():
    """Render content ideas page"""
    st.header("💡 Content Ideas")
    
    with session_scope() as session:
        content = ContentModule(session)
        idea_repo = ContentIdeaRepository(session)
        
        # Stats
        stats = content.get_idea_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Ideas", stats["total_ideas"])
        with col2:
            draft_count = stats["by_status"].get("draft", 0)
            st.metric("Draft", draft_count)
        with col3:
            in_progress = stats["by_status"].get("in_progress", 0)
            st.metric("In Progress", in_progress)
        with col4:
            st.metric("Avg Score", f"{stats['avg_potential_score']:.0f}")
        
        st.markdown("---")
        
        # Tabs
        tab1, tab2, tab3 = st.tabs(["📋 รายการไอเดีย", "➕ เพิ่มไอเดียใหม่", "🤖 คำแนะนำอัตโนมัติ"])
        
        with tab1:
            # Filter
            col1, col2 = st.columns(2)
            with col1:
                status_filter = st.selectbox(
                    "กรองตามสถานะ",
                    ["all", "draft", "in_progress", "scheduled", "published", "archived"],
                )
            with col2:
                priority_filter = st.selectbox(
                    "กรองตาม Priority",
                    ["all", "high", "medium", "low"],
                )
            
            # Get ideas
            if status_filter == "all":
                ideas = idea_repo.get_all(limit=50)
            else:
                ideas = idea_repo.get_by_status(status_filter, limit=50)
            
            if priority_filter != "all":
                ideas = [i for i in ideas if i.priority == priority_filter]
            
            if ideas:
                idea_data = []
                for idea in ideas:
                    idea_data.append({
                        "ID": idea.id,
                        "Title": idea.title[:40] + "..." if len(idea.title) > 40 else idea.title,
                        "Category": idea.category,
                        "Priority": idea.priority,
                        "Score": f"{idea.potential_score:.0f}",
                        "Status": idea.status,
                    })
                st.dataframe(pd.DataFrame(idea_data), use_container_width=True, hide_index=True)
            else:
                st.info("ไม่พบไอเดียที่ตรงกับเงื่อนไข")
        
        with tab2:
            with st.form("new_idea_form"):
                title = st.text_input("ชื่อไอเดีย")
                description = st.text_area("รายละเอียด")
                
                col1, col2 = st.columns(2)
                with col1:
                    category = st.selectbox(
                        "หมวดหมู่",
                        ["tutorial", "review", "vlog", "shorts", "livestream"],
                    )
                with col2:
                    priority = st.selectbox(
                        "Priority",
                        ["high", "medium", "low"],
                    )
                
                potential_score = st.slider("Potential Score", 0, 100, 50)
                
                submitted = st.form_submit_button("บันทึกไอเดีย")
                
                if submitted and title:
                    idea_repo.create(
                        title=title,
                        description=description,
                        category=category,
                        priority=priority,
                        potential_score=potential_score,
                        status="draft",
                    )
                    session.commit()
                    st.success("บันทึกไอเดียสำเร็จ!")
                    st.rerun()
        
        with tab3:
            st.info("ระบบจะวิเคราะห์ข้อมูลและแนะนำไอเดียเนื้อหาโดยอัตโนมัติ")
            
            if st.button("🔄 สร้างคำแนะนำใหม่"):
                with st.spinner("กำลังวิเคราะห์..."):
                    recommendations = content.generate_recommendations(limit=5)
                    
                    if recommendations:
                        for rec in recommendations:
                            st.markdown(f"### 💡 {rec.get('title', 'Untitled')}")
                            st.markdown(f"**หมวดหมู่:** {rec.get('category', '-')}")
                            st.markdown(f"**เหตุผล:** {rec.get('reason', '-')}")
                            st.markdown(f"**Potential Score:** {rec.get('score', 0)}")
                            st.markdown("---")
                    else:
                        st.info("ยังไม่มีข้อมูลเพียงพอสำหรับการแนะนำ")


def render_research_page():
    """Render research page"""
    st.header("🔬 Research & Trends")
    
    with session_scope() as session:
        research = ResearchModule(session)
        research_repo = ResearchItemRepository(session)
        
        # Stats
        stats = research.get_research_stats()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", stats["total_items"])
        with col2:
            st.metric("Actionable", stats["actionable_count"])
        with col3:
            st.metric("Avg Trend Score", f"{stats['avg_trend_score']:.2f}")
        
        st.markdown("---")
        
        # Tabs
        tab1, tab2 = st.tabs(["📋 Research Items", "➕ เพิ่ม Research Item"])
        
        with tab1:
            items = research_repo.get_all(limit=50)
            
            if items:
                item_data = []
                for item in items:
                    item_data.append({
                        "Title": item.title[:40] + "..." if len(item.title) > 40 else item.title,
                        "Source": item.source,
                        "Trend Score": f"{item.trend_score:.2f}",
                        "Actionable": "✅" if item.is_actionable else "❌",
                        "Status": item.status,
                    })
                st.dataframe(pd.DataFrame(item_data), use_container_width=True, hide_index=True)
            else:
                st.info("ยังไม่มี research items")
        
        with tab2:
            with st.form("new_research_form"):
                title = st.text_input("หัวข้อ")
                source = st.selectbox(
                    "แหล่งที่มา",
                    ["youtube_trending", "google_trends", "social_media", "competitor", "other"],
                )
                content_text = st.text_area("เนื้อหา/บันทึก")
                trend_score = st.slider("Trend Score", 0.0, 1.0, 0.5)
                is_actionable = st.checkbox("Actionable")
                
                submitted = st.form_submit_button("บันทึก")
                
                if submitted and title:
                    research_repo.create(
                        title=title,
                        source=source,
                        content=content_text,
                        trend_score=trend_score,
                        is_actionable=is_actionable,
                        status="new",
                    )
                    session.commit()
                    st.success("บันทึกสำเร็จ!")
                    st.rerun()


def render_playbook_page():
    """Render playbook page"""
    st.header("📖 Playbook Rules")
    
    with session_scope() as session:
        playbook = PlaybookModule(session)
        rule_repo = PlaybookRuleRepository(session)
        
        # Stats
        stats = playbook.get_playbook_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Rules", stats["total_rules"])
        with col2:
            st.metric("Active Rules", stats["active_rules"])
        with col3:
            st.metric("Auto Generated", stats["auto_generated"])
        with col4:
            st.metric("Avg Confidence", f"{stats['avg_confidence']:.2f}")
        
        st.markdown("---")
        
        # Active rules
        st.subheader("📋 Active Rules")
        
        active_rules = rule_repo.get_active_rules()
        
        if active_rules:
            for rule in active_rules:
                with st.expander(f"📌 {rule.name} ({rule.category})"):
                    st.markdown(f"**คำอธิบาย:** {rule.description}")
                    st.markdown(f"**Condition:** `{rule.condition}`")
                    st.markdown(f"**Action:** `{rule.action}`")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Confidence", f"{rule.confidence_score:.2f}")
                    with col2:
                        st.metric("Times Applied", rule.times_applied)
                    with col3:
                        st.metric("Success Rate", f"{rule.success_rate:.1%}")
        else:
            st.info("ยังไม่มี active rules")


def render_run_logs_page():
    """Render run logs page"""
    st.header("📜 Run Logs")
    
    with session_scope() as session:
        run_repo = RunLogRepository(session)
        
        # Stats
        stats = run_repo.get_run_stats(days=30)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Runs (30d)", stats["total_runs"])
        with col2:
            st.metric("Completed", stats["completed"])
        with col3:
            st.metric("Failed", stats["failed"])
        with col4:
            st.metric("Success Rate", f"{stats['success_rate']:.1f}%")
        
        st.markdown("---")
        
        # Recent runs
        st.subheader("📋 Recent Runs")
        
        runs = run_repo.get_recent_runs(limit=50)
        
        if runs:
            run_data = []
            for run in runs:
                run_data.append({
                    "Run ID": run.run_id,
                    "Type": run.run_type,
                    "Status": "✅" if run.status == "completed" else "❌" if run.status == "failed" else "🔄",
                    "Started": run.started_at.strftime("%d/%m/%Y %H:%M"),
                    "Duration": f"{run.duration_seconds:.1f}s" if run.duration_seconds else "-",
                    "Items": f"{run.items_succeeded}/{run.items_processed}" if run.items_processed else "-",
                })
            st.dataframe(pd.DataFrame(run_data), use_container_width=True, hide_index=True)
        else:
            st.info("ยังไม่มีประวัติการทำงาน")
        
        # Failed runs
        st.markdown("---")
        st.subheader("❌ Failed Runs")
        
        failed_runs = run_repo.get_failed_runs()
        
        if failed_runs:
            for run in failed_runs[:5]:
                with st.expander(f"❌ {run.run_id}"):
                    st.markdown(f"**Type:** {run.run_type}")
                    st.markdown(f"**Started:** {run.started_at.strftime('%d/%m/%Y %H:%M')}")
                    st.markdown(f"**Error:** {run.error_message}")
        else:
            st.success("ไม่มี failed runs!")


def render_settings_page():
    """Render settings page"""
    st.header("⚙️ Settings")
    
    config = st.session_state.config
    
    # YouTube API Settings
    st.subheader("🎬 YouTube API")
    
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Client Secrets File", config.youtube.oauth.client_secrets_file, disabled=True)
    with col2:
        st.text_input("Token File", config.youtube.oauth.token_file, disabled=True)
    
    st.markdown("---")
    
    # Database Settings
    st.subheader("🗄️ Database")
    st.text_input("Database Path", config.database.path, disabled=True)
    
    st.markdown("---")
    
    # Quick Actions
    st.subheader("🚀 Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Authentication**")
        st.code("python scripts/validate_youtube_auth.py --authenticate")
    
    with col2:
        st.markdown("**Fetch Data**")
        st.code("python scripts/fetch_youtube.py --all")
    
    with col3:
        st.markdown("**Run Analysis**")
        st.code("python scripts/run_all.py --all")


def main():
    """Main function"""
    init_session_state()
    
    page = render_sidebar()
    
    if page == "🏠 หน้าหลัก":
        render_home_page()
    elif page == "📊 YouTube Analytics":
        render_youtube_analytics_page()
    elif page == "📈 Performance Trends":
        render_trends_page()
    elif page == "💡 Content Ideas":
        render_content_page()
    elif page == "🔬 Research":
        render_research_page()
    elif page == "📖 Playbook":
        render_playbook_page()
    elif page == "📜 Run Logs":
        render_run_logs_page()
    elif page == "⚙️ Settings":
        render_settings_page()


if __name__ == "__main__":
    main()
