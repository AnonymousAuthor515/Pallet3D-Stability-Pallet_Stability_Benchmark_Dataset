import pathlib
import json
import pandas as pd 
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix


def logistic_regression_for_all_kpis() -> None: 

    input_dir = pathlib.Path(__file__).parent.parent / "Pallet_Generation" / "Jsons" / "Pallets" 
  
    keys = [
        ["absolute_density"], 
        ["relative_density"], 
        ["side_support"], 
        ["side_support_most_outer_fully_supported"], 
        ["surface_support"], 
        ["min_surface_support"], 
        ["center_of_gravity_2d"], 
        ["center_of_gravity_3d"], 
        ["height_width_ratio"], 
        ["pillar_score"], 
        ["absolute_density", "relative_density", "side_support_most_outer_fully_supported", "surface_support", "center_of_gravity_2d", "center_of_gravity_3d", "height_width_ratio", "pillar_score"]]

    for kpis in keys: 

        rows = []
        for file_path in sorted(input_dir.iterdir()): 
            if not file_path.is_file():
                continue
            
            with open(file_path) as f: 
                packing_plan = json.load(f)

            adams = packing_plan.get("movement_values_adams_fall")
            if adams is None: 
                continue
            adams = adams.get("is_stable")

            kpi = packing_plan.get("KPIs")
            if kpi is None: 
                continue

            row = {}
            row["ground_truth"] = 1 if adams == "True" else 0
            for key in kpis: 
                kpi_value = kpi.get(key)
                if kpi_value is None: 
                    continue
                row[key] = kpi_value

            rows.append(row)
        
        df = pd.DataFrame(rows)
        X = df.drop(columns=["ground_truth"])
        Y = df["ground_truth"]

        model = LogisticRegression(max_iter=1000, verbose=1)
        model.fit(X, Y)

        predictions = model.predict(X)

        tn, fp, fn, tp = confusion_matrix(Y, predictions).ravel()
        specificity = tn / (tn + fp)
        print(f"{kpis}: accuracy: {accuracy_score(Y, predictions)}, precision : {precision_score(Y, predictions)}, recall: {recall_score(Y, predictions)}, f1: {f1_score(Y, predictions)}, specifiy: {specificity}")


if __name__ == "__main__":
    """
    Gives each kpi -including an overall score made of all kpis- its own logistic regression model and calculates the best indicative power regarding ground truth for each kpi. 
    Neccessary to calculate the kpis (benchmark_kpis.py) beforehand
    """
    logistic_regression_for_all_kpis()
    