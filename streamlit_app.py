import streamlit as st
import pandas as pd
import requests
import json

st.title("🎈 CSV to Linear Issue Importer")

def detect_csv_format(df):
    """Detect the format of the CSV based on column names."""
    if all(col in df.columns for col in ['Company Name', 'First Name', 'Last Name', 'Prospect Job Title']):
        return 'original'
    elif all(col in df.columns for col in ['Company name', 'First name', 'Last name', 'Job title']):
        return 'export_contacts'
    else:
        return 'unknown'

def standardize_csv_data(df, csv_format):
    """Standardize CSV data into a consistent format."""
    standardized_data = []
    
    if csv_format == 'original':
        for _, row in df.iterrows():
            standardized_data.append({
                'company': {
                    'name': row['Company Name'],
                    'domain': row['Company Domain Name'],
                    'linkedin': row['Company Linkedin Page'],
                    'revenue': row['Company Revenue'],
                    'year_founded': row['Company Year Founded'],
                    'summary': row['Company Telescope Summary'],
                    'tags': row['Company Telescope Tags'],
                },
                'individual': {
                    'first_name': row['First Name'],
                    'last_name': row['Last Name'],
                    'job_title': row['Prospect Job Title'],
                    'email': row['Email'],
                    'phone': row['Phone Numbers'],
                    'linkedin': row['Linkedin Profile'],
                    'location': f"{row['City']}, {row['State']}, {row['Country']}",
                }
            })
    elif csv_format == 'export_contacts':
        for _, row in df.iterrows():
            standardized_data.append({
                'company': {
                    'name': row['Company name'],
                    'domain': row['Company domain'],
                    'website': row['Company website'],
                    'description': row['Company description'],
                    'year_founded': row['Company year founded'],
                    'employees': row['Company number of employees'],
                    'revenue': row['Company revenue'],
                    'linkedin': row['Company Linkedin URL'],
                    'industry': row['Company industry'],
                    'specialities': row['Company specialities'],
                },
                'individual': {
                    'first_name': row['First name'],
                    'last_name': row['Last name'],
                    'job_title': row['Job title'],
                    'work_email': row['Work email'],
                    'direct_email': row['Direct email'],
                    'phone1': row['Phone 1'],
                    'phone2': row['Phone 2'],
                    'linkedin': row['Linkedin URL'],
                    'location': f"{row['Company city']}, {row['Company state']}, {row['Company country']}",
                    'seniority': row['Seniority'],
                    'departments': row['Departments'],
                }
            })
    
    return standardized_data

def format_company_description(company):
    return "\n".join([f"{key.replace('_', ' ').title()}: {value}" for key, value in company.items() if value])

def format_individual_description(individual):
    return "\n".join([f"{key.replace('_', ' ').title()}: {value}" for key, value in individual.items() if value])

def create_or_update_linear_issues(standardized_data, api_key):
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    url = "https://api.linear.app/graphql"

    st.write("Starting the import process...")

    # Initialize statistics
    stats = {
        "companies_processed": 0,
        "companies_created": 0,
        "companies_existing": 0,
        "individuals_processed": 0,
        "individuals_created": 0,
        "individuals_existing": 0
    }

    # Get the team ID
    with st.spinner("Fetching team information..."):
        query = """
        query {
            teams {
                nodes {
                    id
                    name
                }
            }
        }
        """
        response = requests.post(url, json={"query": query}, headers=headers)
        response_data = response.json()
        if "errors" in response_data:
            st.error(f"Error fetching team information: {response_data['errors']}")
            return
        team_id = response_data["data"]["teams"]["nodes"][0]["id"]

    total_companies = len(set(item['company']['name'] for item in standardized_data))
    st.write(f"Found {total_companies} unique companies in the CSV.")

    # Create a progress bar for companies
    company_progress = st.progress(0)

    processed_companies = set()

    for index, item in enumerate(standardized_data, 1):
        company = item['company']
        individual = item['individual']

        if company['name'] not in processed_companies:
            # Update company progress bar
            company_progress.progress(len(processed_companies) / total_companies)

            stats["companies_processed"] += 1
            processed_companies.add(company['name'])

            # Check if company issue already exists
            company_search_query = """
            query($teamId: ID!, $title: String!) {
                issues(
                    filter: {team: {id: {eq: $teamId}}, title: {eq: $title}}
                    first: 1
                ) {
                    nodes {
                        id
                        title
                    }
                }
            }
            """
            variables = {
                "teamId": team_id,
                "title": company['name']
            }
            response = requests.post(url, json={"query": company_search_query, "variables": variables}, headers=headers)
            response_data = response.json()
            if "errors" in response_data:
                st.error(f"Error searching for company issue: {response_data['errors']}")
                continue
            existing_company_issues = response_data["data"]["issues"]["nodes"]

            if existing_company_issues:
                company_issue_id = existing_company_issues[0]["id"]
                stats["companies_existing"] += 1
            else:
                # Create new company issue
                company_mutation = """
                mutation($title: String!, $description: String!, $teamId: String!) {
                    issueCreate(input: {title: $title, description: $description, teamId: $teamId}) {
                        success
                        issue {
                            id
                        }
                    }
                }
                """
                variables = {
                    "title": company['name'],
                    "description": format_company_description(company),
                    "teamId": team_id
                }
                response = requests.post(url, json={"query": company_mutation, "variables": variables}, headers=headers)
                response_data = response.json()
                if "errors" in response_data:
                    st.error(f"Error creating company issue: {response_data['errors']}")
                    continue
                result = response_data["data"]["issueCreate"]
                if result["success"]:
                    company_issue_id = result["issue"]["id"]
                    stats["companies_created"] += 1
                else:
                    st.error(f"Failed to create issue for {company['name']}")
                    continue

        # Process individual
        stats["individuals_processed"] += 1

        individual_title = f"{individual['first_name']} {individual['last_name']} - {individual['job_title']}"
        
        # Check if individual issue already exists
        individual_search_query = """
        query($teamId: ID!, $title: String!, $parentId: ID!) {
            issues(
                filter: {team: {id: {eq: $teamId}}, title: {eq: $title}, parent: {id: {eq: $parentId}}}
                first: 1
            ) {
                nodes {
                    id
                    title
                }
            }
        }
        """
        variables = {
            "teamId": team_id,
            "title": individual_title,
            "parentId": company_issue_id
        }
        response = requests.post(url, json={"query": individual_search_query, "variables": variables}, headers=headers)
        response_data = response.json()
        if "errors" in response_data:
            st.error(f"Error searching for individual issue: {response_data['errors']}")
            continue
        existing_individual_issues = response_data["data"]["issues"]["nodes"]

        if existing_individual_issues:
            stats["individuals_existing"] += 1
        else:
            # Create new individual issue
            individual_mutation = """
            mutation($title: String!, $description: String!, $teamId: String!, $parentId: String!) {
                issueCreate(input: {title: $title, description: $description, teamId: $teamId, parentId: $parentId}) {
                    success
                }
            }
            """
            variables = {
                "title": individual_title,
                "description": format_individual_description(individual),
                "teamId": team_id,
                "parentId": company_issue_id
            }
            response = requests.post(url, json={"query": individual_mutation, "variables": variables}, headers=headers)
            response_data = response.json()
            if "errors" in response_data:
                st.error(f"Error creating individual issue: {response_data['errors']}")
            elif response_data["data"]["issueCreate"]["success"]:
                stats["individuals_created"] += 1
            else:
                st.error(f"Failed to create issue for {individual_title}")

    # Clear the company progress bar after processing all companies
    company_progress.empty()

    st.success("All issues created or updated successfully in Linear!")

    # Display statistics in a table
    st.write("Import Statistics:")
    stats_df = pd.DataFrame({
        "Category": ["Companies", "Companies", "Companies", "Individuals", "Individuals", "Individuals"],
        "Action": ["Processed", "Created", "Already Existing", "Processed", "Created", "Already Existing"],
        "Count": [
            stats['companies_processed'],
            stats['companies_created'],
            stats['companies_existing'],
            stats['individuals_processed'],
            stats['individuals_created'],
            stats['individuals_existing']
        ]
    })
    st.table(stats_df)

# File uploader
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    csv_format = detect_csv_format(df)
    
    if csv_format == 'unknown':
        st.error("Unknown CSV format. Please use a supported format.")
    else:
        st.write(f"Detected CSV format: {csv_format}")
        standardized_data = standardize_csv_data(df, csv_format)
        st.write("CSV file loaded and standardized successfully. Here's a preview:")
        st.write(pd.DataFrame(standardized_data[:5]))
        st.write(f"Total rows in CSV: {len(standardized_data)}")

        # Linear API Key input
        api_key = st.text_input("Enter your Linear API Key", type="password")

        if st.button("Import to Linear"):
            if api_key:
                with st.spinner("Importing data to Linear..."):
                    create_or_update_linear_issues(standardized_data, api_key)
            else:
                st.error("Please enter your Linear API Key")

st.write(
    "This app imports leads from a CSV file into Linear, creating or updating company issues with individual sub-issues."
)
