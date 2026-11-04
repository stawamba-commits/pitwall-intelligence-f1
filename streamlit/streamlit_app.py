"""PitWall Analytics · dashboard on the GOLD tables (course: 08-visualisation/streamlit).

Inside Snowflake (nothing to install): Snowsight > Projects > Streamlit > + Streamlit App,
warehouse PITWALL_BI_WH, database PITWALL, schema GOLD, role PITWALL_ANALYST, paste this file.
On a laptop: pip install streamlit "snowflake-connector-python[pandas]==4.8.0", fill .streamlit/secrets.toml
(not committed) and run `streamlit run streamlit_app.py`.
"""
import streamlit as st

G = "PITWALL.GOLD"


@st.cache_data(ttl=600)        # re-query at most every 10 minutes: dashboards must not burn credits
def load(sql):
    try:
        from snowflake.snowpark.context import get_active_session    # running inside Snowflake
        df = get_active_session().sql(sql).to_pandas()
    except Exception:
        df = st.connection("snowflake").query(sql)                    # running on a laptop
    df.columns = [c.lower() for c in df.columns]
    return df


st.set_page_config(page_title="PitWall Analytics", layout="wide")
nxt = load(f"SELECT race_id, race_name, race_date, circuit_ref FROM {G}.DIM_RACE WHERE is_next_race")
if nxt.empty:
    st.error("No next race in the calendar.")
    st.stop()
race = nxt.iloc[0]
st.title(f"PitWall Analytics · {race['race_name']} ({race['race_date']})")
fresh = load(f"SELECT MAX(scored_at) AS t FROM {G}.UC1_PODIUM_PREDICTIONS WHERE race_id = '{race['race_id']}'")
st.caption(f"Data up to {fresh['t'].iloc[0]} · source: {G} (gold layer, refreshed daily at 07:00 Paris)")

# UC1 ----------------------------------------------------------------------------------
st.header("1 · Who will finish on the podium?")
pred = load(f"""SELECT p.predicted_rank, d.driver_name, c.constructor_name, p.p_podium, p.grid_known
                FROM {G}.UC1_PODIUM_PREDICTIONS p
                JOIN {G}.DIM_DRIVER d ON d.driver_ref = p.driver_ref
                LEFT JOIN {G}.UC1_PODIUM_FEATURES f ON f.race_id = p.race_id AND f.driver_ref = p.driver_ref
                LEFT JOIN {G}.DIM_CONSTRUCTOR c ON c.constructor_ref = f.constructor_ref
                WHERE p.race_id = '{race['race_id']}' ORDER BY p.predicted_rank""")
if not pred.empty and not pred["grid_known"].any():
    st.info("Prediction made BEFORE qualifying: it will be updated once the grid is known.")
st.dataframe(pred.head(10), hide_index=True, use_container_width=True)
bt = load(f"SELECT season, races, model_hit_rate, grid_hit_rate, accepted FROM {G}.UC1_MODEL_BACKTEST")
st.caption("Backtest: share of real podium finishers found by the model vs by the grid order")
st.dataframe(bt, hide_index=True)

c1, c2 = st.columns(2)
# UC4 ----------------------------------------------------------------------------------
with c1:
    st.header("4 · Rain alert")
    st.dataframe(load(f"""SELECT session, starts_at, max_rain_probability, rain_mm, alert_level,
                                 wet_races || ' wet / ' || past_races || ' past races' AS history
                          FROM {G}.UC4_RAIN_ALERT"""), hide_index=True)
# UC5 ----------------------------------------------------------------------------------
with c2:
    st.header("5 · Safety-car risk here")
    st.dataframe(load(f"""SELECT races, races_with_sc_or_vsc, sc_or_vsc_rate FROM {G}.UC5_SAFETY_CAR_RISK
                          WHERE circuit_ref = '{race['circuit_ref']}'"""), hide_index=True)

# UC3 ----------------------------------------------------------------------------------
st.header("3 · Usual pit strategy at this circuit (last 3 seasons)")
st.dataframe(load(f"SELECT races, avg_stops, usual_stops, compounds_used FROM {G}.UC3_PIT_STRATEGY "
                  f"WHERE circuit_ref = '{race['circuit_ref']}'"), hide_index=True)

# UC2 ----------------------------------------------------------------------------------
st.header("2 · Biggest climbers of the season")
st.bar_chart(load(f"""SELECT driver_name, SUM(places_gained) AS places_gained FROM {G}.UC2_PLACES_GAINED
                      WHERE season = YEAR('{race['race_date']}'::date) GROUP BY 1 ORDER BY 2 DESC LIMIT 10"""),
             x="driver_name", y="places_gained")
