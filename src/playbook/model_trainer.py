"""
Model Trainer - ฝึก Interpretable Models สำหรับ Playbook Learning

รองรับ models:
1. Logistic Regression - สำหรับ classification (high/low performer)
2. Linear Regression - สำหรับ regression (predict views, CTR)
3. Decision Tree - สำหรับ interpretable rules
4. Random Forest - สำหรับ feature importance

Output:
- Feature importance scores
- Model coefficients (for linear models)
- Decision rules (for tree models)
"""

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_squared_error, mean_absolute_error, r2_score,
    classification_report, confusion_matrix,
)
from rich.console import Console
from rich.table import Table

console = Console()


class PlaybookModelTrainer:
    """
    Playbook Model Trainer - ฝึก interpretable models
    
    การใช้งาน:
        trainer = PlaybookModelTrainer()
        trainer.fit(df, target='is_high_performer', task='classification')
        importance = trainer.get_feature_importance()
        rules = trainer.extract_rules()
    """
    
    def __init__(self, model_dir: str = "models"):
        """
        สร้าง Model Trainer
        
        Args:
            model_dir: โฟลเดอร์สำหรับเก็บ models
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.scaler = None
        self.feature_names: List[str] = []
        self.target_name: str = ""
        self.task: str = ""  # 'classification' or 'regression'
        self.model_type: str = ""
        
        # Training results
        self.train_metrics: Dict[str, float] = {}
        self.test_metrics: Dict[str, float] = {}
        self.cv_scores: List[float] = []
        self.feature_importance: Dict[str, float] = {}
        
    def _prepare_data(
        self,
        df: pd.DataFrame,
        target: str,
        features: Optional[List[str]] = None,
        test_size: float = 0.2,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """เตรียมข้อมูลสำหรับ training"""
        
        # Select features
        if features is None:
            # Use all numeric columns except target and ID columns
            exclude_cols = [target, 'video_id', 'youtube_video_id', 'performance_tier']
            features = [col for col in df.columns 
                       if df[col].dtype in ['int64', 'float64', 'bool']
                       and col not in exclude_cols]
        
        self.feature_names = features
        self.target_name = target
        
        # Prepare X and y
        X = df[features].fillna(0).values
        y = df[target].values
        
        # Convert boolean to int
        if y.dtype == bool:
            y = y.astype(int)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        return X_train_scaled, X_test_scaled, y_train, y_test
    
    def fit_classification(
        self,
        df: pd.DataFrame,
        target: str = 'is_high_performer',
        features: Optional[List[str]] = None,
        model_type: str = 'logistic',
        **kwargs,
    ) -> Dict[str, Any]:
        """
        ฝึก classification model
        
        Args:
            df: DataFrame ที่มี features และ target
            target: ชื่อ column ที่เป็น target
            features: รายชื่อ features (None = ใช้ทั้งหมด)
            model_type: 'logistic', 'tree', 'forest'
            **kwargs: parameters สำหรับ model
            
        Returns:
            Dictionary ของ metrics และ results
        """
        self.task = 'classification'
        self.model_type = model_type
        
        console.print(f"[cyan]🎯 กำลังฝึก Classification Model ({model_type})...[/cyan]")
        
        # Prepare data
        X_train, X_test, y_train, y_test = self._prepare_data(df, target, features)
        
        console.print(f"   📊 Training samples: {len(X_train)}")
        console.print(f"   📊 Test samples: {len(X_test)}")
        console.print(f"   📊 Features: {len(self.feature_names)}")
        
        # Create model
        if model_type == 'logistic':
            self.model = LogisticRegression(
                max_iter=1000,
                class_weight='balanced',
                random_state=42,
                **kwargs
            )
        elif model_type == 'tree':
            self.model = DecisionTreeClassifier(
                max_depth=kwargs.get('max_depth', 5),
                min_samples_leaf=kwargs.get('min_samples_leaf', 10),
                class_weight='balanced',
                random_state=42,
            )
        elif model_type == 'forest':
            self.model = RandomForestClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 5),
                min_samples_leaf=kwargs.get('min_samples_leaf', 10),
                class_weight='balanced',
                random_state=42,
                n_jobs=-1,
            )
        else:
            raise ValueError(f"ไม่รองรับ model_type: {model_type}")
        
        # Train
        self.model.fit(X_train, y_train)
        
        # Predict
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)
        
        # Calculate metrics
        self.train_metrics = {
            'accuracy': accuracy_score(y_train, y_train_pred),
            'precision': precision_score(y_train, y_train_pred, zero_division=0),
            'recall': recall_score(y_train, y_train_pred, zero_division=0),
            'f1': f1_score(y_train, y_train_pred, zero_division=0),
        }
        
        self.test_metrics = {
            'accuracy': accuracy_score(y_test, y_test_pred),
            'precision': precision_score(y_test, y_test_pred, zero_division=0),
            'recall': recall_score(y_test, y_test_pred, zero_division=0),
            'f1': f1_score(y_test, y_test_pred, zero_division=0),
        }
        
        # Cross-validation
        self.cv_scores = cross_val_score(self.model, X_train, y_train, cv=5).tolist()
        
        # Feature importance
        self._calculate_feature_importance()
        
        # Print results
        self._print_classification_results(y_test, y_test_pred)
        
        return {
            'train_metrics': self.train_metrics,
            'test_metrics': self.test_metrics,
            'cv_scores': self.cv_scores,
            'feature_importance': self.feature_importance,
        }
    
    def fit_regression(
        self,
        df: pd.DataFrame,
        target: str = 'views',
        features: Optional[List[str]] = None,
        model_type: str = 'linear',
        **kwargs,
    ) -> Dict[str, Any]:
        """
        ฝึก regression model
        
        Args:
            df: DataFrame ที่มี features และ target
            target: ชื่อ column ที่เป็น target
            features: รายชื่อ features (None = ใช้ทั้งหมด)
            model_type: 'linear', 'ridge', 'tree', 'forest'
            **kwargs: parameters สำหรับ model
            
        Returns:
            Dictionary ของ metrics และ results
        """
        self.task = 'regression'
        self.model_type = model_type
        
        console.print(f"[cyan]📈 กำลังฝึก Regression Model ({model_type})...[/cyan]")
        
        # Prepare data
        X_train, X_test, y_train, y_test = self._prepare_data(df, target, features)
        
        # Log transform for views (if target is views)
        if target in ['views', 'likes', 'comments']:
            y_train = np.log1p(y_train)
            y_test = np.log1p(y_test)
        
        console.print(f"   📊 Training samples: {len(X_train)}")
        console.print(f"   📊 Test samples: {len(X_test)}")
        console.print(f"   📊 Features: {len(self.feature_names)}")
        
        # Create model
        if model_type == 'linear':
            self.model = LinearRegression(**kwargs)
        elif model_type == 'ridge':
            self.model = Ridge(alpha=kwargs.get('alpha', 1.0), **kwargs)
        elif model_type == 'tree':
            self.model = DecisionTreeRegressor(
                max_depth=kwargs.get('max_depth', 5),
                min_samples_leaf=kwargs.get('min_samples_leaf', 10),
                random_state=42,
            )
        elif model_type == 'forest':
            self.model = RandomForestRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 5),
                min_samples_leaf=kwargs.get('min_samples_leaf', 10),
                random_state=42,
                n_jobs=-1,
            )
        else:
            raise ValueError(f"ไม่รองรับ model_type: {model_type}")
        
        # Train
        self.model.fit(X_train, y_train)
        
        # Predict
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)
        
        # Calculate metrics
        self.train_metrics = {
            'mse': mean_squared_error(y_train, y_train_pred),
            'mae': mean_absolute_error(y_train, y_train_pred),
            'r2': r2_score(y_train, y_train_pred),
        }
        
        self.test_metrics = {
            'mse': mean_squared_error(y_test, y_test_pred),
            'mae': mean_absolute_error(y_test, y_test_pred),
            'r2': r2_score(y_test, y_test_pred),
        }
        
        # Cross-validation
        self.cv_scores = cross_val_score(self.model, X_train, y_train, cv=5, scoring='r2').tolist()
        
        # Feature importance
        self._calculate_feature_importance()
        
        # Print results
        self._print_regression_results()
        
        return {
            'train_metrics': self.train_metrics,
            'test_metrics': self.test_metrics,
            'cv_scores': self.cv_scores,
            'feature_importance': self.feature_importance,
        }
    
    def _calculate_feature_importance(self):
        """คำนวณ feature importance"""
        importance_dict = {}
        
        if hasattr(self.model, 'coef_'):
            # Linear models
            coef = self.model.coef_
            if len(coef.shape) > 1:
                coef = coef[0]  # For logistic regression
            
            for name, imp in zip(self.feature_names, coef):
                importance_dict[name] = float(imp)
                
        elif hasattr(self.model, 'feature_importances_'):
            # Tree-based models
            for name, imp in zip(self.feature_names, self.model.feature_importances_):
                importance_dict[name] = float(imp)
        
        # Sort by absolute importance
        self.feature_importance = dict(
            sorted(importance_dict.items(), key=lambda x: abs(x[1]), reverse=True)
        )
    
    def _print_classification_results(self, y_true, y_pred):
        """แสดงผลลัพธ์ classification"""
        console.print("\n[green]✅ ผลการฝึก Classification Model[/green]")
        
        # Metrics table
        table = Table(title="📊 Model Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Train", justify="right")
        table.add_column("Test", justify="right")
        
        for metric in ['accuracy', 'precision', 'recall', 'f1']:
            table.add_row(
                metric.capitalize(),
                f"{self.train_metrics[metric]:.4f}",
                f"{self.test_metrics[metric]:.4f}",
            )
        
        console.print(table)
        
        # CV scores
        console.print(f"\n📈 Cross-Validation Scores: {np.mean(self.cv_scores):.4f} (+/- {np.std(self.cv_scores):.4f})")
        
        # Top features
        self._print_top_features()
    
    def _print_regression_results(self):
        """แสดงผลลัพธ์ regression"""
        console.print("\n[green]✅ ผลการฝึก Regression Model[/green]")
        
        # Metrics table
        table = Table(title="📊 Model Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Train", justify="right")
        table.add_column("Test", justify="right")
        
        table.add_row("MSE", f"{self.train_metrics['mse']:.4f}", f"{self.test_metrics['mse']:.4f}")
        table.add_row("MAE", f"{self.train_metrics['mae']:.4f}", f"{self.test_metrics['mae']:.4f}")
        table.add_row("R²", f"{self.train_metrics['r2']:.4f}", f"{self.test_metrics['r2']:.4f}")
        
        console.print(table)
        
        # CV scores
        console.print(f"\n📈 Cross-Validation R² Scores: {np.mean(self.cv_scores):.4f} (+/- {np.std(self.cv_scores):.4f})")
        
        # Top features
        self._print_top_features()
    
    def _print_top_features(self, top_n: int = 10):
        """แสดง top features"""
        console.print(f"\n[cyan]🔝 Top {top_n} Features (by importance)[/cyan]")
        
        table = Table()
        table.add_column("Rank", style="dim")
        table.add_column("Feature", style="cyan")
        table.add_column("Importance", justify="right")
        table.add_column("Direction", justify="center")
        
        for i, (name, imp) in enumerate(list(self.feature_importance.items())[:top_n], 1):
            direction = "🔼 Positive" if imp > 0 else "🔽 Negative"
            table.add_row(str(i), name, f"{imp:.4f}", direction)
        
        console.print(table)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """คืนค่า feature importance"""
        return self.feature_importance
    
    def get_top_positive_features(self, n: int = 5) -> List[Tuple[str, float]]:
        """คืนค่า top positive features"""
        positive = [(k, v) for k, v in self.feature_importance.items() if v > 0]
        return sorted(positive, key=lambda x: x[1], reverse=True)[:n]
    
    def get_top_negative_features(self, n: int = 5) -> List[Tuple[str, float]]:
        """คืนค่า top negative features"""
        negative = [(k, v) for k, v in self.feature_importance.items() if v < 0]
        return sorted(negative, key=lambda x: x[1])[:n]
    
    def extract_tree_rules(self) -> str:
        """ดึง rules จาก Decision Tree"""
        if not isinstance(self.model, (DecisionTreeClassifier, DecisionTreeRegressor)):
            return "Model ไม่ใช่ Decision Tree"
        
        return export_text(self.model, feature_names=self.feature_names)
    
    def save_model(self, name: str = "playbook_model") -> str:
        """บันทึก model"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.pkl"
        filepath = self.model_dir / filename
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'target_name': self.target_name,
            'task': self.task,
            'model_type': self.model_type,
            'train_metrics': self.train_metrics,
            'test_metrics': self.test_metrics,
            'feature_importance': self.feature_importance,
            'timestamp': timestamp,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        console.print(f"[green]✅ บันทึก model สำเร็จ: {filepath}[/green]")
        return str(filepath)
    
    def load_model(self, filepath: str):
        """โหลด model"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.target_name = model_data['target_name']
        self.task = model_data['task']
        self.model_type = model_data['model_type']
        self.train_metrics = model_data['train_metrics']
        self.test_metrics = model_data['test_metrics']
        self.feature_importance = model_data['feature_importance']
        
        console.print(f"[green]✅ โหลด model สำเร็จ: {filepath}[/green]")
    
    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """ทำนายจาก DataFrame"""
        if self.model is None:
            raise ValueError("ยังไม่ได้ฝึก model")
        
        X = df[self.feature_names].fillna(0).values
        X_scaled = self.scaler.transform(X)
        
        return self.model.predict(X_scaled)
    
    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """ทำนาย probability (สำหรับ classification)"""
        if self.task != 'classification':
            raise ValueError("predict_proba ใช้ได้เฉพาะ classification")
        
        X = df[self.feature_names].fillna(0).values
        X_scaled = self.scaler.transform(X)
        
        return self.model.predict_proba(X_scaled)
