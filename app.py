
import os
from datetime import date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

st.set_page_config(
    page_title="LicenseTrack",
    page_icon="📋",
    layout="wide",
)


def create_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Check your .env file for Supabase credentials.")
        st.stop()

    return create_client(SUPABASE_URL, SUPABASE_KEY)


supabase = create_supabase_client()


def logout():
    st.session_state.pop("access_token", None)
    st.session_state.pop("refresh_token", None)
    st.session_state.pop("user_email", None)
    st.rerun()


def get_data(table_name):
    return (
        supabase.table(table_name)
        .select("*")
        .execute()
        .data
        or []
    )


def load_business_data():
    companies = get_data("companies")
    branches = get_data("branches")
    lto_records = get_data("lto_records")

    return companies, branches, lto_records


# -------------------------
# LOGIN
# -------------------------

st.title("📋 LicenseTrack")
st.caption("NMDPRA Licence to Operate management")

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if not st.session_state.access_token:
    st.subheader("Sign in")

    with st.form("login_form"):
        email = st.text_input("Email address")
        password = st.text_input(
            "Password",
            type="password",
        )
        login_clicked = st.form_submit_button(
            "Sign in",
            type="primary",
        )

    if login_clicked:
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email.strip(),
                "password": password,
            })

            session = response.session

            if session:
                st.session_state.access_token = (
                    session.access_token
                )
                st.session_state.refresh_token = (
                    session.refresh_token
                )
                st.session_state.user_email = email.strip()
                st.rerun()
            else:
                st.error("Login failed. Please try again.")

        except Exception:
            st.error(
                "Unable to sign in. Check your email, password, "
                "and Supabase authentication settings."
            )

    st.stop()


# Restore the signed-in session after Streamlit reruns.
try:
    response = supabase.auth.set_session(
        st.session_state.access_token,
        st.session_state.refresh_token,
    )

    if response.session:
        st.session_state.access_token = (
            response.session.access_token
        )
        st.session_state.refresh_token = (
            response.session.refresh_token
        )

except Exception:
    logout()


# -------------------------
# LOAD DATA
# -------------------------

try:
    companies, branches, lto_records = load_business_data()
except Exception:
    st.error(
        "Could not load records. Check your database security "
        "policies and signed-in user's profile."
    )
    st.stop()


company_by_id = {
    company["id"]: company["company_name"]
    for company in companies
}

branch_by_id = {
    branch["id"]: branch
    for branch in branches
}

lto_by_branch = {
    record["branch_id"]: record
    for record in lto_records
}

today = date.today()

expiring_soon = [
    record
    for record in lto_records
    if 0 <= (
        date.fromisoformat(record["expiry_date"]) - today
    ).days <= 30
]

expired_records = [
    record
    for record in lto_records
    if (
        date.fromisoformat(record["expiry_date"]) < today
        and record["renewal_status"] != "cancelled"
    )
]


# -------------------------
# HEADER AND SUMMARY
# -------------------------

header_col, logout_col = st.columns([5, 1])

with header_col:
    st.subheader("Dashboard")
    st.caption(
        f"Signed in as {st.session_state.get('user_email', '')}"
    )

with logout_col:
    if st.button("Sign out"):
        logout()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Companies", len(companies))
col2.metric("Branches", len(branches))
col3.metric("LTO records", len(lto_records))
col4.metric("Expiring within 30 days", len(expiring_soon))

st.divider()

overview_tab, company_tab, branch_tab, lto_tab = st.tabs([
    "Overview",
    "Add company",
    "Add branch",
    "Manage LTO",
])


# -------------------------
# OVERVIEW
# -------------------------

with overview_tab:
    st.subheader("LTO expiry overview")

    if not lto_records:
        st.info(
            "No LTO records yet. Add a company, register its "
            "branches, and enter their LTO expiry dates."
        )
    else:
        rows = []

        for record in lto_records:
            branch = branch_by_id.get(record["branch_id"], {})
            company_name = company_by_id.get(
                branch.get("company_id"),
                "Unknown company",
            )

            expiry = date.fromisoformat(record["expiry_date"])
            days_left = (expiry - today).days

            if record["renewal_status"] == "cancelled":
                expiry_label = "Cancelled"
            elif days_left < 0:
                expiry_label = "Expired"
            elif days_left == 0:
                expiry_label = "Expires today"
            else:
                expiry_label = f"{days_left} days left"

            rows.append({
                "Company": company_name,
                "Branch": branch.get("branch_name", ""),
                "LTO Reference": record.get("lto_reference") or "",
                "Expiry Date": expiry.isoformat(),
                "Time Remaining": expiry_label,
                "Status": record["renewal_status"],
            })

        df = pd.DataFrame(rows)
        df["Expiry Date"] = pd.to_datetime(df["Expiry Date"])

        st.dataframe(
            df.sort_values("Expiry Date"),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Branches expiring within 30 days")

    if expiring_soon:
        for record in sorted(
            expiring_soon,
            key=lambda item: item["expiry_date"],
        ):
            branch = branch_by_id.get(record["branch_id"], {})
            company_name = company_by_id.get(
                branch.get("company_id"),
                "Unknown company",
            )
            days_left = (
                date.fromisoformat(record["expiry_date"]) - today
            ).days

            st.warning(
                f"**{company_name} — {branch.get('branch_name', '')}**"
                f" | Expires: {record['expiry_date']}"
                f" | {days_left} day(s) remaining"
            )
    else:
        st.success("No LTO records expire within the next 30 days.")


# -------------------------
# ADD COMPANY
# -------------------------

with company_tab:
    st.subheader("Register a client company")

    with st.form("company_form", clear_on_submit=True):
        company_name = st.text_input(
            "Company name *",
            placeholder="e.g. Remi Station Limited",
        )
        contact_name = st.text_input("Contact person")
        phone = st.text_input("Phone number")
        email = st.text_input("Email address")

        submitted = st.form_submit_button(
            "Save company",
            type="primary",
        )

    if submitted:
        if not company_name.strip():
            st.error("Company name is required.")
        else:
            try:
                supabase.table("companies").insert({
                    "company_name": company_name.strip(),
                    "contact_name": contact_name.strip() or None,
                    "phone": phone.strip() or None,
                    "email": email.strip() or None,
                }).execute()

                st.success("Company registered successfully.")
                st.rerun()

            except Exception as error:
                st.error(f"Could not save company: {error}")


# -------------------------
# ADD BRANCH
# -------------------------

with branch_tab:
    st.subheader("Register a branch")

    if not companies:
        st.info("Register a company before adding its branches.")
    else:
        company_options = {
            company["company_name"]: company["id"]
            for company in companies
        }

        with st.form("branch_form", clear_on_submit=True):
            selected_company = st.selectbox(
                "Client company *",
                list(company_options.keys()),
            )
            branch_name = st.text_input(
                "Branch name *",
                placeholder="e.g. Ikeja",
            )
            address = st.text_input("Branch address")

            submitted = st.form_submit_button(
                "Save branch",
                type="primary",
            )

        if submitted:
            if not branch_name.strip():
                st.error("Branch name is required.")
            else:
                try:
                    supabase.table("branches").insert({
                        "company_id": company_options[selected_company],
                        "branch_name": branch_name.strip(),
                        "address": address.strip() or None,
                    }).execute()

                    st.success(
                        f"{branch_name.strip()} branch registered."
                    )
                    st.rerun()

                except Exception as error:
                    st.error(
                        "Could not save branch. Check whether this "
                        "company already has a branch with that name. "
                        f"Details: {error}"
                    )


# -------------------------
# ADD OR RENEW LTO
# -------------------------

with lto_tab:
    st.subheader("Add or update a branch's LTO")

    if not branches:
        st.info("Register at least one branch first.")
    else:
        branch_options = {}

        for branch in branches:
            company_name = company_by_id.get(
                branch["company_id"],
                "Unknown company",
            )
            label = f"{company_name} — {branch['branch_name']}"
            branch_options[label] = branch["id"]

        with st.form("lto_form"):
            selected_branch = st.selectbox(
                "Select branch *",
                list(branch_options.keys()),
            )

            branch_id = branch_options[selected_branch]
            existing = lto_by_branch.get(branch_id, {})

            if existing:
                st.info(
                    "This branch already has an LTO record. "
                    "Saving will update that record's details "
                    "instead of creating another current record."
                )

            lto_reference = st.text_input(
                "LTO reference number",
                value=existing.get("lto_reference") or "",
            )

            issue_date = st.date_input(
                "Issue date (optional)",
                value=None,
            )

            expiry_date = st.date_input(
                "Expiry date *",
                value=(
                    date.fromisoformat(existing["expiry_date"])
                    if existing
                    else date.today()
                ),
            )

            status_options = [
                "active",
                "renewal_in_progress",
                "expired",
                "cancelled",
            ]

            current_status = existing.get(
                "renewal_status",
                "active",
            )

            status_index = (
                status_options.index(current_status)
                if current_status in status_options
                else 0
            )

            renewal_status = st.selectbox(
                "Renewal status",
                status_options,
                index=status_index,
            )

            submitted = st.form_submit_button(
                "Save LTO / Update renewal",
                type="primary",
            )

        if submitted:
            payload = {
                "branch_id": branch_id,
                "lto_reference": lto_reference.strip() or None,
                "issue_date": (
                    issue_date.isoformat()
                    if issue_date
                    else None
                ),
                "expiry_date": expiry_date.isoformat(),
                "renewal_status": renewal_status,
                "updated_at": date.today().isoformat(),
            }

            try:
                supabase.table("lto_records").upsert(
                    payload,
                    on_conflict="branch_id",
                ).execute()

                st.success(
                    "LTO record saved successfully. "
                    "The branch's current record has been updated."
                )
                st.rerun()

            except Exception as error:
                st.error(f"Could not save LTO record: {error}")
