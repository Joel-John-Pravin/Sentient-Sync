#!/usr/bin/env python
"""
Train LSTM-CNN Model on CIC-IDS2017 for IEEE Paper
"""

import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import (
    Input, LSTM, Conv1D, MaxPooling1D, 
    Flatten, Dense, Dropout, Concatenate,
    BatchNormalization, GlobalAveragePooling1D
)
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import (
    EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
)
from tensorflow.keras.utils import to_categorical
from sklearn.metrics import (
    classification_report, confusion_matrix, 
    accuracy_score, precision_score, recall_score, f1_score
)
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import os

print("=" * 60)
print("Training LSTM-CNN for IEEE Paper")
print("=" * 60)

# 1. Load preprocessed data
print("\n1. Loading preprocessed data...")
X_train = np.load('processed_data/X_train.npy')
X_test = np.load('processed_data/X_test.npy')
y_train = np.load('processed_data/y_train.npy')
y_test = np.load('processed_data/y_test.npy')

# Load metadata
scaler = joblib.load('processed_data/scaler.pkl')
label_encoder = joblib.load('processed_data/label_encoder.pkl')

with open('processed_data/class_names.txt', 'r') as f:
    class_names = [line.strip() for line in f.readlines()]

print(f"X_train shape: {X_train.shape}")
print(f"X_test shape: {X_test.shape}")
print(f"Number of classes: {len(class_names)}")
print(f"Classes: {class_names}")

# 2. Convert labels to categorical
print("\n2. Preparing labels...")
y_train_cat = to_categorical(y_train, num_classes=len(class_names))
y_test_cat = to_categorical(y_test, num_classes=len(class_names))

# 3. Build LSTM-CNN Hybrid Model
print("\n3. Building LSTM-CNN model...")

def create_lstm_cnn_model(input_shape, num_classes):
    # Input layer
    inputs = Input(shape=input_shape)
    
    # CNN Branch - extracts spatial features
    cnn = Conv1D(filters=64, kernel_size=3, activation='relu', padding='same')(inputs)
    cnn = BatchNormalization()(cnn)
    cnn = MaxPooling1D(pool_size=2)(cnn)
    
    cnn = Conv1D(filters=128, kernel_size=3, activation='relu', padding='same')(cnn)
    cnn = BatchNormalization()(cnn)
    cnn = MaxPooling1D(pool_size=2)(cnn)
    
    cnn = Conv1D(filters=256, kernel_size=3, activation='relu', padding='same')(cnn)
    cnn = BatchNormalization()(cnn)
    cnn = GlobalAveragePooling1D()(cnn)
    
    # LSTM Branch - extracts temporal patterns
    lstm = LSTM(units=128, return_sequences=True)(inputs)
    lstm = BatchNormalization()(lstm)
    lstm = LSTM(units=64, return_sequences=True)(lstm)
    lstm = BatchNormalization()(lstm)
    lstm = LSTM(units=32, return_sequences=False)(lstm)
    
    # Concatenate both branches
    concat = Concatenate()([cnn, lstm])
    
    # Dense layers for classification
    dense = Dense(128, activation='relu')(concat)
    dense = BatchNormalization()(dense)
    dense = Dropout(0.5)(dense)
    
    dense = Dense(64, activation='relu')(dense)
    dense = BatchNormalization()(dense)
    dense = Dropout(0.3)(dense)
    
    # Output layer
    outputs = Dense(num_classes, activation='softmax')(dense)
    
    model = Model(inputs=inputs, outputs=outputs)
    return model

# Get input shape
input_shape = (X_train.shape[1], X_train.shape[2])
model = create_lstm_cnn_model(input_shape, len(class_names))

# Compile model
model.compile(
    optimizer=Adam(learning_rate=0.001),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

# Model summary
model.summary()

# 4. Define callbacks
print("\n4. Setting up callbacks...")
callbacks = [
    EarlyStopping(
        monitor='val_loss',
        patience=10,
        restore_best_weights=True,
        verbose=1
    ),
    ModelCheckpoint(
        'best_model.h5',
        monitor='val_accuracy',
        save_best_only=True,
        verbose=1
    ),
    ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=5,
        min_lr=0.00001,
        verbose=1
    )
]

# 5. Train model
print("\n5. Training model...")
history = model.fit(
    X_train, y_train_cat,
    validation_data=(X_test, y_test_cat),
    epochs=50,
    batch_size=64,
    callbacks=callbacks,
    verbose=1
)

# 6. Evaluate model
print("\n6. Evaluating model...")
y_pred = model.predict(X_test)
y_pred_classes = np.argmax(y_pred, axis=1)
y_true_classes = y_test

# Calculate metrics
accuracy = accuracy_score(y_true_classes, y_pred_classes)
precision = precision_score(y_true_classes, y_pred_classes, average='weighted')
recall = recall_score(y_true_classes, y_pred_classes, average='weighted')
f1 = f1_score(y_true_classes, y_pred_classes, average='weighted')

print("\n" + "=" * 60)
print("📊 MODEL PERFORMANCE METRICS")
print("=" * 60)
print(f"Accuracy:  {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")
print(f"F1-Score:  {f1:.4f}")
print("=" * 60)

# Per-class metrics
print("\n📊 Per-Class Classification Report:")
print(classification_report(
    y_true_classes, 
    y_pred_classes, 
    target_names=class_names,
    digits=4
))

# 7. Plot confusion matrix
print("\n7. Generating confusion matrix...")
cm = confusion_matrix(y_true_classes, y_pred_classes)

plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
            xticklabels=class_names, yticklabels=class_names)
plt.title('Confusion Matrix - LSTM-CNN on CIC-IDS2017')
plt.xlabel('Predicted')
plt.ylabel('True')
plt.tight_layout()
plt.savefig('confusion_matrix.png', dpi=300)
plt.show()

# 8. Plot training history
print("\n8. Plotting training history...")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Accuracy plot
axes[0].plot(history.history['accuracy'], label='Train')
axes[0].plot(history.history['val_accuracy'], label='Validation')
axes[0].set_title('Model Accuracy')
axes[0].set_xlabel('Epoch')
axes[0].set_ylabel('Accuracy')
axes[0].legend()
axes[0].grid(True)

# Loss plot
axes[1].plot(history.history['loss'], label='Train')
axes[1].plot(history.history['val_loss'], label='Validation')
axes[1].set_title('Model Loss')
axes[1].set_xlabel('Epoch')
axes[1].set_ylabel('Loss')
axes[1].legend()
axes[1].grid(True)

plt.tight_layout()
plt.savefig('training_history.png', dpi=300)
plt.show()

# 9. Save results for paper
print("\n9. Saving results...")
results = {
    'accuracy': accuracy,
    'precision': precision,
    'recall': recall,
    'f1_score': f1,
    'confusion_matrix': cm.tolist(),
    'class_names': class_names
}

import json
with open('paper_results.json', 'w') as f:
    json.dump(results, f, indent=2)

# Save the model
model.save('lstm_cnn_final_model.h5')
print("Model saved as 'lstm_cnn_final_model.h5'")

print("\n" + "=" * 60)
print("✅ Training complete!")
print("Results saved for IEEE paper:")
print("  - confusion_matrix.png")
print("  - training_history.png")
print("  - paper_results.json")
print("  - lstm_cnn_final_model.h5")
print("=" * 60)