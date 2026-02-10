import matplotlib.pyplot as plt
import pandas as pd
import os
import seaborn as sns
from datetime import datetime

class WaferMapGenerator:
    def __init__(self, result_file="Wafer_Sort_Results.csv"):
        self.result_file = result_file
        self.output_folder = "results"
        os.makedirs(self.output_folder, exist_ok=True)

    def generate_static_map(self):
        if not os.path.exists(self.result_file):
            return None

        try:
            df = pd.read_csv(self.result_file)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return None
            
        if df.empty:
            return None

        # Deduplicate: Keep last Test_Time for each (Row, Col)
        # Assuming Test_Time is sortable string
        df = df.sort_values('Test_Time').drop_duplicates(subset=['Row', 'Col'], keep='last')

        # Pivot for heatmap
        # Value to plot: Final_Result mapped to numbers?
        # Green(PASS)=1, Yellow(PARTIAL)=2, Red(FAIL)=3
        result_map = {'PASS': 1, 'PARTIAL': 2, 'FAIL': 3}
        df['Color_Code'] = df['Final_Result'].map(result_map).fillna(0)
        
        pivot_table = df.pivot(index='Row', columns='Col', values='Color_Code')
        
        plt.figure(figsize=(10, 8))
        # Custom cmap: 0=Empty(White), 1=Green, 2=Yellow, 3=Red
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(['white', 'green', 'yellow', 'red'])
        
        # We need to ensure the data range covers 0-3 for the colormap to work correctly if some values are missing
        # A trick is to set vmin=0, vmax=3
        ax = sns.heatmap(pivot_table, cmap=cmap, vmin=0, vmax=3, annot=True, fmt='g', 
                         cbar=False, linewidths=.5, linecolor='gray')
        
        plt.title('Wafer Sort Map')
        plt.xlabel('Column')
        plt.ylabel('Row')
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Wafer_Map_{timestamp}.png"
        filepath = os.path.join(self.output_folder, filename)
        plt.savefig(filepath)
        plt.close()
        print(f"Wafer Map saved to {filepath}")
        return filepath
