import json
import os
import pandas as pd
import seaborn as sn
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report
from tqdm import tqdm

# Import the RAGChatbot class from your main app file
# Make sure your main file is named app.py or change 'app' to your file's name
try:
    from main import RAGChatbot
except ImportError:
    print("Error: Could not import RAGChatbot from app.py.")
    print("Make sure this script is in the same directory as your app.py")
    exit()

EVALUATION_FILE = "evaluation_data.json"
INTENTS_FILE = "intents.json"

def run_evaluation():
    print("Starting evaluation...")

    # 1. Initialize the bot
    if not os.path.exists(INTENTS_FILE):
        print(f"Error: {INTENTS_FILE} not found.")
        return
        
    print("Loading RAGChatbot...")
    # We pass the intents_path just like in your app.py
    bot = RAGChatbot(intents_path=INTENTS_FILE)
    
    # 2. Load evaluation data
    if not os.path.exists(EVALUATION_FILE):
        print(f"Error: {EVALUATION_FILE} not found.")
        print("Please create it first (see documentation).")
        return
        
    with open(EVALUATION_FILE, 'r', encoding='utf-8') as f:
        eval_data = json.load(f)

    print(f"Loaded {len(eval_data)} test cases from {EVALUATION_FILE}.")

    # 3. Get all possible intent labels from the bot
    # This is important for the confusion matrix axes
    all_labels = sorted(list(bot.intents.keys()) + ["general_fallback"])

    # 4. Run predictions
    y_true = []
    y_pred = []

    print("Running intent classification on test data...")
    # Using tqdm for a nice progress bar
    for item in tqdm(eval_data):
        user_text = item["text"]
        true_intent = item["true_intent"]
        
        # Call the bot's internal classification function
        predicted_intent = bot._evaluate_intent_with_llm(user_text)
        
        y_true.append(true_intent)
        y_pred.append(predicted_intent)

    print("Evaluation complete.")
    print("-" * 30)

    # 5. Print Classification Report (Text summary)
    print("Classification Report:")
    # 'zero_division=0' prevents errors if an intent is never predicted
    report = classification_report(y_true, y_pred, labels=all_labels, zero_division=0)
    print(report)
    print("-" * 30)

    # 6. Generate and Draw Confusion Matrix
    print("Generating confusion matrix...")
    cm = confusion_matrix(y_true, y_pred, labels=all_labels)
    
    # Use pandas and seaborn for a nice-looking plot
    df_cm = pd.DataFrame(cm, 
                         index = [i for i in all_labels],
                         columns = [i for i in all_labels])
    
    plt.figure(figsize=(12, 10))
    sn.heatmap(df_cm, annot=True, fmt='g', cmap='Blues') # 'fmt='g'' disables scientific notation
    plt.title('Chatbot Intent Classification Confusion Matrix')
    plt.ylabel('True Intent')
    plt.xlabel('Predicted Intent')
    
    # Adjust layout to prevent labels from being cut off
    plt.tight_layout()
    
    # Save the plot to a file
    output_filename = "confusion_matrix.png"
    plt.savefig(output_filename)
    
    print(f"✅ Confusion matrix plot saved as '{output_filename}'")
    
    # Optionally, display the plot
    # plt.show() 

if __name__ == "__main__":
    run_evaluation()