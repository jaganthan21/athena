import pandas as pd

# Read the two CSV files (replace 'file1.csv' and 'file2.csv' with your actual file paths)
df1 = pd.read_csv(r"C:\Users\Mekkanos\Downloads\check_20250911_224056\output_check_20250911_224101.csv")
df2 = pd.read_csv(r"C:\Users\Mekkanos\Downloads\check_20250911_224817\output_check_20250911_224826.csv")

# Assume the common key column for matching rows is 'Name' (change if different)
key_column = 'P_Surname'

# Assume the three columns to compare are 'Age', 'City', and 'Salary' (change to your actual columns)
compare_columns = ['RF_FirstName', 'RF_Surname', 'RF_Role']

# Merge the dataframes on the key column
merged = df1.merge(df2, on=key_column, suffixes=('_1', '_2'))

# Find rows where any of the compare columns differ
diff_mask = pd.Series([False] * len(merged), index=merged.index)
for col in compare_columns:
    diff_mask |= (merged[f'{col}_1'] != merged[f'{col}_2'])

# Get the rows with differences
differences = merged[diff_mask]

# Print the differences
if differences.empty:
    print("No differences found.")
else:
    for idx, row in differences.iterrows():
        key_value = row[key_column]
        print(f"For {key_column} = {key_value}:")
        for col in compare_columns:
            val1 = row[f'{col}_1']
            val2 = row[f'{col}_2']
            if val1 != val2:
                print(f"  {col} differs: '{val1}' vs '{val2}'")
        print()