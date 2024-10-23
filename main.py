from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
import pandas as pd
import numpy as np
import os
import shutil

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html") as f:
        return f.read()

# Sample CSV creation for demonstration
@app.get("/create-sample-csv")
async def create_sample_csv(file_path: str = "data/sample_data.csv"):
    data = {
        "Title": ["The Impacts of the use of Thematic & Chronologic Multi-modal Information Representation on Sequential and Global Students’ Historical Understanding", "Bob", "Charlie","Learning Experience with LearnwithEmma","Backup Automation Using Power Automate for Malaysian Vaccination Centres"],
        "Submission ID": [236,250,264],
        "DOI": ["10.33093/jiwe.2022.1.1.4", "10.33093/jiwe.2022.1.1.1", "10.33093/jiwe.2022.1.1.5"]
    }
    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df.to_csv(file_path, index=False)
    return {"message": f"CSV file created at {file_path}"}

@app.get("/download-csv")
async def download_csv(file_path: str):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="CSV file not found.")

    return FileResponse(file_path, media_type='text/csv', filename=os.path.basename(file_path))

def process_csv(df):
    # Ensure 'DOI' column exists and is a string
    if 'DOI' in df.columns:
        df['DOI'] = df['DOI'].astype(str).fillna('')

    # Add the specified columns with NaN values if not present
    columns_to_assign_nan = [
        'No (All)', 'No', 'Month', 'DOI', 'Journal Name', 'Year Published', 'Volume', 'Issues', 
        'Types', 'Page', 'Page (start)', 'Page (end)', 'DOI/URL', 'Paper Title', 
        'Full Authors (Institution published)'
    ]
    for col in columns_to_assign_nan:
        if col not in df.columns:
            df[col] = np.nan
    # Reorder DataFrame columns
    df = df[columns_to_assign_nan + [col for col in df.columns if col not in columns_to_assign_nan]]

    # Process the DOI column if it contains valid data
    if 'DOI' in df.columns:
        # Extracting the last segment of DOI
        df['No'] = df['DOI'].str.split('.').str[-1]
        # Mapping for Journal Names
        example_dict = {
            'jiwe': 'Journal of Informatics and Web Engineering',
            'jetap': 'Journal of Engineering Technology and Applied Physics',
            'ijoras': 'International Journal on Robotics, Automation and Sciences',
            'ijcm': 'International Journal of Creative Multimedia',
            'ijomfa': 'International Journal of Management, Finance and Accounting',
            'ipbss': 'Issues and Perspectives in Business and Social Sciences',
            'ajlp': 'Asian Journal of Law and Policy',
            'jclc': 'Journal of Communication, Language and Culture'
        }

        # Extract journal name from DOI
        journal_name = df['DOI'].str.split('/').str[1].str.split('.').str[0]
        df['Journal Name'] = journal_name.map(example_dict)

        # Extract other details from DOI
        df['Year Published'] = df['DOI'].str.split('.').str[2]
        df['Volume'] = df['DOI'].str.split('.').str[3]
        df['Issues'] = df['DOI'].str.split('.').str[4]
        df['DOI/URL'] = 'https://doi.org/' + df['DOI'] 
        df['Paper Title'] = df['Title'] if 'Title' in df.columns else np.nan

        # Drop the 'Title' column if it exists
        if 'Title' in df.columns:
            df = df.drop('Title', axis=1)

    # Handle author details (if applicable)
    given_name_cols = [col for col in df.columns if 'Given Name (Author' in col]
    df['Full Authors (Institution published)'] = df['Full Authors (Institution published)'].fillna('').astype(str)
    for i in range(len(given_name_cols)):
        last_name = df['Given Name (Author ' + str(i + 1) + ')'].fillna('').astype(str)
        family_name = df['Family Name (Author ' + str(i + 1) + ')'].fillna('').astype(str)
        affiliation = df['Affiliation (Author ' + str(i + 1) + ')'].fillna('').astype(str)
        full_name = last_name + ' ' + family_name
        name_aff = full_name.where(affiliation == '', full_name + ' (' + affiliation + ')')
        df['Full Authors (Institution published)'] = df['Full Authors (Institution published)'].str.cat(
            name_aff, sep=', ', na_rep='').str.strip(', ')

    # Split DOI to sort
    split_df = df['DOI'].str.split('.').apply(lambda x: [int(i) if i.isdigit() else np.nan for i in x[2:6]] if isinstance(x, list) else [np.nan]*4)
    split_df = pd.DataFrame(split_df.tolist(), columns=['Year', 'Part1', 'Part2', 'Part3'])

    # Sort DataFrame and remove temporary columns
    df = df.join(split_df)
    df = df.sort_values(by=['Year', 'Part1', 'Part2', 'Part3'], na_position='last').reset_index(drop=True)
    df = df.drop(['Year', 'Part1', 'Part2', 'Part3'], axis=1)
    df['No (All)'] = range(1,len(df)+1)
    return df

@app.post("/process-csv/")
async def process_csv_endpoint(file: UploadFile = File(...)):
    # Create a temporary directory to save the uploaded file
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)

    file_path = os.path.join(temp_dir, file.filename)
    
    # Save the uploaded file
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Load the CSV file into a DataFrame
    df = pd.read_csv(file_path)

    # Process the DataFrame
    processed_df = process_csv(df)

    # Save the processed DataFrame to a new CSV file
    processed_file_path = os.path.join(temp_dir, f"processed2_{file.filename}")
    processed_df.to_csv(processed_file_path, index=False)

    # Return the processed file as a response
    return FileResponse(processed_file_path, media_type='text/csv', filename=os.path.basename(processed_file_path))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
