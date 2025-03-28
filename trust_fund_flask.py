from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import text
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trust_fund.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Database Models
@dataclass
class Donor(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(100), nullable=False)
    email: str = db.Column(db.String(120), nullable=False)
    amount: float = db.Column(db.Float, nullable=False)
    category: str = db.Column(db.String(50), nullable=False)
    payment_method: str = db.Column(db.String(20), nullable=False, default='upi')
    payment_status: str = db.Column(db.String(20), nullable=False, default='pending')
    date: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    message: Optional[str] = db.Column(db.Text, nullable=True)

@dataclass
class Distribution(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    beneficiary_name: str = db.Column(db.String(100), nullable=False)
    amount: float = db.Column(db.Float, nullable=False)
    category: str = db.Column(db.String(50), nullable=False)
    date: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    purpose: str = db.Column(db.Text, nullable=False)
    status: str = db.Column(db.String(20), nullable=False, default='pending')
    payment_mode: str = db.Column(db.String(50), nullable=False, default='cash')

# Create all database tables
with app.app_context():
    db.create_all()

def get_form_data(form: Dict[str, Any], field: str, default: Any = None) -> Any:
    """Helper function to safely get form data"""
    return form.get(field, default)

@app.route('/')
def index():
    donations = db.session.query(Donor).order_by(text('date DESC')).all()
    distributions = db.session.query(Distribution).order_by(text('date DESC')).all()
    
    total_donations = sum(d.amount for d in donations)
    total_distributions = sum(d.amount for d in distributions)
    balance = total_donations - total_distributions
    
    categories: Dict[str, Dict[str, float]] = {
        'education': {'donations': 0.0, 'distributions': 0.0},
        'healthcare': {'donations': 0.0, 'distributions': 0.0},
        'food': {'donations': 0.0, 'distributions': 0.0},
        'shelter': {'donations': 0.0, 'distributions': 0.0},
        'emergency': {'donations': 0.0, 'distributions': 0.0}
    }
    
    for donation in donations:
        if donation.category in categories:
            categories[donation.category]['donations'] += donation.amount
            
    for distribution in distributions:
        if distribution.category in categories:
            categories[distribution.category]['distributions'] += distribution.amount
    
    return render_template('index.html', 
                         donations=donations,
                         distributions=distributions,
                         total_donations=total_donations,
                         total_distributions=total_distributions,
                         balance=balance,
                         categories=categories)

@app.route('/donate', methods=['GET', 'POST'])
def donate():
    if request.method == 'POST':
        try:
            form_data = request.form
            donor = Donor(
                name=get_form_data(form_data, 'name'),
                email=get_form_data(form_data, 'email'),
                amount=float(get_form_data(form_data, 'amount', 0)),
                category=get_form_data(form_data, 'category'),
                payment_method=get_form_data(form_data, 'payment_method', 'upi'),
                message=get_form_data(form_data, 'message', '')
            )
            
            if not all([donor.name, donor.email, donor.amount, donor.category]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('donate'))
                
            db.session.add(donor)
            db.session.commit()
            
            # Simulate payment processing
            if donor.payment_method == 'upi':
                flash('Please complete your UPI payment using the QR code.', 'info')
            elif donor.payment_method == 'card':
                flash('You will be redirected to the secure payment gateway.', 'info')
            else:
                flash('Please complete your payment using net banking.', 'info')
                
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error processing donation: {str(e)}', 'error')
            return redirect(url_for('donate'))
    
    return render_template('donate.html')

@app.route('/distribute', methods=['GET', 'POST'])
def distribute():
    if request.method == 'POST':
        try:
            form_data = request.form
            distribution_amount = float(get_form_data(form_data, 'amount', 0))
            
            # Calculate current balance
            donations = Donor.query.filter_by(payment_status='completed').all()
            distributions = Distribution.query.filter_by(status='completed').all()
            total_donations = sum(d.amount for d in donations)
            total_distributions = sum(d.amount for d in distributions)
            current_balance = total_donations - total_distributions
            
            # Check if distribution amount exceeds available balance
            if distribution_amount > current_balance:
                flash(f'Distribution amount (₹{distribution_amount:,.2f}) exceeds available balance (₹{current_balance:,.2f})', 'error')
                return redirect(url_for('distribute'))
            
            distribution = Distribution(
                beneficiary_name=get_form_data(form_data, 'beneficiary_name'),
                amount=distribution_amount,
                category=get_form_data(form_data, 'category'),
                purpose=get_form_data(form_data, 'purpose'),
                payment_mode=get_form_data(form_data, 'payment_mode', 'cash'),
                status='completed'
            )
            
            if not all([distribution.beneficiary_name, distribution.amount, distribution.category, distribution.purpose]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('distribute'))
                
            db.session.add(distribution)
            db.session.commit()
            flash('Distribution recorded successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error recording distribution: {str(e)}', 'error')
            return redirect(url_for('distribute'))
    
    return render_template('distribute.html')

@app.route('/api/stats')
def get_stats():
    donations = Donor.query.filter_by(payment_status='completed').all()
    distributions = Distribution.query.filter_by(status='completed').all()
    
    total_donations = sum(d.amount for d in donations)
    total_distributions = sum(d.amount for d in distributions)
    
    return jsonify({
        'total_donations': total_donations,
        'total_distributions': total_distributions,
        'balance': total_donations - total_distributions
    })

if __name__ == '__main__':
    app.run(debug=True, port=5002) 