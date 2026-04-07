#!/usr/bin/env python
"""
Preprocess CIC-IDS2017 for LSTM-CNN model
With memory-efficient SMOTE
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from imblearn.over_sampling import SMOTE
import joblib
import os
import glob
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("Preprocessing CIC-IDS2017 Dataset")
print("=" * 60)

# 1. Find and load the dataset
print("\n1. Loading dataset...")
parquet_files = glob.glob('CIC-IDS2017/**/*.parquet', recursive=True)
print(f"Found parquet files: {parquet_files}")

file_path = parquet_files[0]
print(f"Loading: {file_path}")
df = pd.read_parquet(file_path, engine='pyarrow')

print(f"✅ Loaded {len(df):,} flow records")

# 2. Use label column
label_col = 'attack_label'
print(f"\n2. Using label column: '{label_col}'")

# 3. Group rare attacks
print("\n3. Grouping rare attack types...")
def group_attacks(label):
    if label == 'BENIGN':
        return 'BENIGN'
    elif 'DoS' in label or 'DDoS' in label:
        return 'DoS/DDoS'
    elif 'Web Attack' in label:
        return 'Web_Attack'
    elif 'Bot' in label:
        return 'Bot'
    elif 'PortScan' in label:
        return 'PortScan'
    elif 'FTP' in label or 'SSH' in label:
        return 'Brute_Force'
    elif 'Heartbleed' in label or 'Infiltration' in label:
        return 'Rare_Attacks'
    else:
        return 'Other'

df['attack_group'] = df[label_col].apply(group_attacks)

# Show distribution
group_dist = df['attack_group'].value_counts()
print("\nGrouped class distribution:")
for group, count in group_dist.items():
    print(f"  {group}: {count:,} ({count/len(df)*100:.2f}%)")

# 4. Clean data
print("\n4. Cleaning data...")
df = df.replace([np.inf, -np.inf], np.nan)
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
df = df.dropna(subset=numeric_cols)
print(f"After cleaning: {len(df):,} records")

# 5. Select features
print("\n5. Selecting features...")
columns_to_drop = [
    'flow_id', 'source_ip', 'destination_ip', 'Timestamp',
    'attack_label', 'attack_group',
]

feature_cols = [col for col in numeric_cols 
                if col not in columns_to_drop]
print(f"Selected {len(feature_cols)} numeric features")

X = df[feature_cols].values
y = df['attack_group'].values

# 6. Encode labels
print("\n6. Encoding labels...")
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)
class_names = label_encoder.classes_
n_classes = len(class_names)

print(f"Final classes ({n_classes} classes):")
for i, name in enumerate(class_names):
    count = sum(y_encoded == i)
    print(f"  {i}: {name} ({count:,} samples, {count/len(y_encoded)*100:.2f}%)")

# 7. Scale features (use subset to save memory)
print("\n7. Scaling features (using 500k samples)...")
# Use a subset for scaling to save memory
sample_idx = np.random.choice(len(X), size=min(500000, len(X)), replace=False)
scaler = StandardScaler()
scaler.fit(X[sample_idx])

# Transform all data in batches
print("Transforming all data in batches...")
batch_size = 100000
X_scaled_list = []
for i in range(0, len(X), batch_size):
    end = min(i + batch_size, len(X))
    batch = X[i:end]
    X_scaled_list.append(scaler.transform(batch))
    print(f"  Processed {end}/{len(X)} rows")

X_scaled = np.vstack(X_scaled_list)
print(f"✅ Scaled shape: {X_scaled.shape}")

# 8. Apply SMOTE with sampling strategy
print("\n8. Applying SMOTE for class balancing...")

# Calculate target samples (limit to avoid memory issues)
max_samples_per_class = 100000  # Limit each class to 100k samples
sampling_strategy = {}

for i, class_name in enumerate(class_names):
    current_count = sum(y_encoded == i)
    target_count = min(max_samples_per_class, current_count * 2)  # Double minority classes
    if current_count < target_count:
        sampling_strategy[i] = target_count
    print(f"  {class_name}: {current_count} -> {target_count if i in sampling_strategy else current_count}")

# Apply SMOTE with limited strategy
smote = SMOTE(random_state=42, sampling_strategy=sampling_strategy, k_neighbors=min(3, min(sampling_strategy.values())-1))
X_resampled, y_resampled = smote.fit_resample(X_scaled, y_encoded)

print("\nAfter SMOTE:")
for i in range(n_classes):
    count = sum(y_resampled == i)
    print(f"  {class_names[i]}: {count:,} samples")

# 9. Create sequences for LSTM
print("\n9. Creating sequences for LSTM...")
def create_sequences(data, labels, seq_length=20):
    X_seq, y_seq = [], []
    for i in range(0, len(data) - seq_length, seq_length):
        X_seq.append(data[i:i+seq_length])
        y_seq.append(labels[i+seq_length])
    return np.array(X_seq), np.array(y_seq)

X_seq, y_seq = create_sequences(X_resampled, y_resampled)
print(f"Sequence shape: {X_seq.shape}")
print(f"Labels shape: {y_seq.shape}")

# 10. Train-test split
print("\n10. Splitting data...")
X_train, X_test, y_train, y_test = train_test_split(
    X_seq, y_seq, test_size=0.2, random_state=42, stratify=y_seq
)

print(f"Train: {X_train.shape[0]:,} sequences")
print(f"Test: {X_test.shape[0]:,} sequences")

# 11. Save processed data
print("\n11. Saving processed data...")
os.makedirs('processed_data', exist_ok=True)

# Save in chunks to avoid memory issues
np.save('processed_data/X_train.npy', X_train)
np.save('processed_data/X_test.npy', X_test)
np.save('processed_data/y_train.npy', y_train)
np.save('processed_data/y_test.npy', y_test)

# Save metadata
joblib.dump(scaler, 'processed_data/scaler.pkl')
joblib.dump(label_encoder, 'processed_data/label_encoder.pkl')

with open('processed_data/feature_names.txt', 'w') as f:
    for name in feature_cols:
        f.write(f"{name}\n")

with open('processed_data/class_names.txt', 'w') as f:
    for name in class_names:
        f.write(f"{name}\n")

print("\n" + "=" * 60)
print("📊 DATASET STATISTICS FOR PAPER")
print("=" * 60)
print(f"  Original samples: {len(df):,}")
print(f"  Features: {len(feature_cols)}")
print(f"  Original classes: 15")
print(f"  Grouped classes: {n_classes}")
print(f"  After SMOTE: {len(X_resampled):,}")
print(f"  Sequences: {len(X_seq):,}")
print(f"  Sequence length: 20")
print(f"  Training sequences: {len(X_train):,}")
print(f"  Testing sequences: {len(X_test):,}")
print("=" * 60)

print("\n✅ Preprocessing complete!")
print("Files saved in ./processed_data/")
print("\nNext: Run train_model.py to train your LSTM-CNN")