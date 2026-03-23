"""
ICT/SMC COMPLETE TRADING SYSTEM
Ready to run - just copy and paste!
"""

import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class ICTTradingSystem:
    """Complete ICT/SMC Trading System"""
    
    def __init__(self, data):
        self.data = data.copy()
        if 'datetime' in self.data.columns:
            self.data['datetime'] = pd.to_datetime(self.data['datetime'])
            self.data.set_index('datetime', inplace=True)
        
        # Calculate all indicators
        self._calculate_indicators()
        self._calculate_orb()
        
    def _calculate_indicators(self):
        """Calculate all technical indicators"""
        
        # VWAP
        tp = (self.data['high'] + self.data['low'] + self.data['close']) / 3
        cum_tp_vol = (tp * self.data['volume']).cumsum()
        cum_vol = self.data['volume'].cumsum()
        self.data['vwap'] = cum_tp_vol / cum_vol
        
        # Bollinger Bands (Standard Deviation)
        self.data['sma'] = self.data['close'].rolling(20).mean()
        self.data['std'] = self.data['close'].rolling(20).std()
        self.data['upper'] = self.data['sma'] + (self.data['std'] * 2)
        self.data['lower'] = self.data['sma'] - (self.data['std'] * 2)
        
        # Wick Theory
        self.data['upper_wick'] = self.data['high'] - np.maximum(self.data['close'], self.data['open'])
        self.data['lower_wick'] = np.minimum(self.data['close'], self.data['open']) - self.data['low']
        self.data['range'] = self.data['high'] - self.data['low']
        self.data['wick_ratio'] = self.data['lower_wick'] / (self.data['range'] + 1e-10)
        self.data['rejection'] = (self.data['wick_ratio'] > 0.6) & (self.data['close'] > self.data['open'])
        
        # ATR for risk
        tr = pd.concat([
            self.data['high'] - self.data['low'],
            abs(self.data['high'] - self.data['close'].shift()),
            abs(self.data['low'] - self.data['close'].shift())
        ], axis=1).max(axis=1)
        self.data['atr'] = tr.rolling(14).mean()
        
        # MFI
        mf = tp * self.data['volume']
        pos = np.where(tp > tp.shift(1), mf, 0)
        neg = np.where(tp < tp.shift(1), mf, 0)
        pos_sum = pd.Series(pos).rolling(14).sum()
        neg_sum = pd.Series(neg).rolling(14).sum()
        ratio = pos_sum / (neg_sum + 1e-10)
        self.data['mfi'] = 100 - (100 / (1 + ratio))
        
        # Sessions
        self.data['hour'] = self.data.index.hour
        self.data['minute'] = self.data.index.minute
        self.data['kill_zone'] = ((self.data['hour'] == 7) & (self.data['minute'] >= 30)) | \
                                   ((self.data['hour'] >= 8) & (self.data['hour'] < 10))
    
    def _calculate_orb(self):
        """Opening Range Breakout"""
        self.data['date'] = self.data.index.date
        self.data['orb_high'] = np.nan
        self.data['orb_low'] = np.nan
        
        for date in self.data['date'].unique():
            day = self.data[self.data['date'] == date]
            orb = day[(day.index.hour == 8) & (day.index.minute <= 30)]
            if len(orb) > 0:
                self.data.loc[self.data['date'] == date, 'orb_high'] = orb['high'].max()
                self.data.loc[self.data['date'] == date, 'orb_low'] = orb['low'].min()
        
        self.data['breakout'] = (self.data['high'] > self.data['orb_high']) & (self.data['orb_high'].notna())
        self.data['ote_buy'] = self.data['low'].rolling(50).min() + \
                                (self.data['high'].rolling(50).max() - self.data['low'].rolling(50).min()) * 0.705
    
    def generate_signals(self):
        """Generate trading signals"""
        signals = []
        
        for i in range(50, len(self.data)):
            buy = 0
            sell = 0
            reasons = []
            
            # Buy conditions
            if self.data['rejection'].iloc[i]:
                buy += 2
                reasons.append('Wick Rejection')
            
            if abs(self.data['close'].iloc[i] - self.data['vwap'].iloc[i]) / self.data['vwap'].iloc[i] < 0.005:
                buy += 1.5
                reasons.append('VWAP Support')
            
            if self.data['breakout'].iloc[i]:
                buy += 2
                reasons.append('ORB Breakout')
            
            if self.data['close'].iloc[i] <= self.data['lower'].iloc[i]:
                buy += 1.5
                reasons.append('Oversold')
            
            if self.data['close'].iloc[i] <= self.data['ote_buy'].iloc[i]:
                buy += 2
                reasons.append('OTE Zone')
            
            if self.data['mfi'].iloc[i] < 30:
                buy += 1.5
                reasons.append('MFI Oversold')
            
            if self.data['kill_zone'].iloc[i]:
                buy += 1
                reasons.append('Kill Zone')
            
            # Sell conditions
            if self.data['close'].iloc[i] > self.data['vwap'].iloc[i] * 1.01:
                sell += 1.5
                reasons.append('VWAP Resistance')
            
            if self.data['close'].iloc[i] >= self.data['upper'].iloc[i]:
                sell += 1.5
                reasons.append('Overbought')
            
            if self.data['mfi'].iloc[i] > 70:
                sell += 1.5
                reasons.append('MFI Overbought')
            
            # Decision
            action = 'HOLD'
            confidence = 0
            
            if buy >= 6 and buy > sell:
                action = 'BUY'
                confidence = min(100, buy * 12)
            elif sell >= 6 and sell > buy:
                action = 'SELL'
                confidence = min(100, sell * 12)
            
            signals.append({
                'timestamp': self.data.index[i],
                'price': self.data['close'].iloc[i],
                'action': action,
                'confidence': confidence,
                'reasons': ', '.join(reasons[:4])
            })
        
        return pd.DataFrame(signals)
    
    def plot(self, days=5):
        """Plot chart with signals"""
        data = self.data.tail(days * 288)
        signals = self.generate_signals().tail(days * 288)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
        
        # Price chart
        ax1.plot(data.index, data['close'], 'w-', label='Price', linewidth=1)
        ax1.plot(data.index, data['vwap'], 'y-', label='VWAP', alpha=0.7)
        ax1.plot(data.index, data['upper'], 'r--', alpha=0.5, label='Upper')
        ax1.plot(data.index, data['lower'], 'g--', alpha=0.5, label='Lower')
        
        # Signals
        buys = signals[signals['action'] == 'BUY']
        sells = signals[signals['action'] == 'SELL']
        ax1.scatter(buys['timestamp'], buys['price'], color='green', marker='^', s=100, label='BUY')
        ax1.scatter(sells['timestamp'], sells['price'], color='red', marker='v', s=100, label='SELL')
        
        ax1.set_ylabel('Price')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_title('ICT Trading System - Price Action')
        
        # MFI
        ax2.plot(data.index, data['mfi'], 'orange', linewidth=1)
        ax2.axhline(70, color='r', linestyle='--')
        ax2.axhline(30, color='g', linestyle='--')
        ax2.fill_between(data.index, 30, 70, alpha=0.1)
        ax2.set_ylabel('MFI')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)
        ax2.set_title('Money Flow Index')
        
        plt.tight_layout()
        plt.show()

class Backtester:
    """Backtest the strategy"""
    
    def __init__(self, strategy, capital=10000, risk=0.02):
        self.strategy = strategy
        self.capital = capital
        self.risk = risk
        self.trades = []
    
    def run(self):
        signals = self.strategy.generate_signals()
        capital = self.capital
        position = None
        
        for _, row in signals.iterrows():
            if not position and row['action'] != 'HOLD' and row['confidence'] >= 70:
                atr = self.strategy.data.loc[row['timestamp'], 'atr']
                
                if row['action'] == 'BUY':
                    stop = row['price'] - (atr * 1.5)
                    tp = row['price'] + (atr * 2)
                else:
                    stop = row['price'] + (atr * 1.5)
                    tp = row['price'] - (atr * 2)
                
                risk_amount = capital * self.risk
                size = risk_amount / abs(row['price'] - stop)
                
                position = {
                    'entry_time': row['timestamp'],
                    'type': row['action'],
                    'entry': row['price'],
                    'stop': stop,
                    'tp': tp,
                    'size': size
                }
                
            elif position:
                price = row['price']
                exited = False
                
                if position['type'] == 'BUY':
                    if price <= position['stop']:
                        pnl = (position['stop'] - position['entry']) * position['size']
                        exited = True
                    elif price >= position['tp']:
                        pnl = (position['tp'] - position['entry']) * position['size']
                        exited = True
                else:
                    if price >= position['stop']:
                        pnl = (position['entry'] - position['stop']) * position['size']
                        exited = True
                    elif price <= position['tp']:
                        pnl = (position['entry'] - position['tp']) * position['size']
                        exited = True
                
                if exited:
                    position['exit_time'] = row['timestamp']
                    position['pnl'] = pnl
                    self.trades.append(position)
                    capital += pnl
                    position = None
        
        return self.trades
    
    def results(self):
        if not self.trades:
            return {}
        
        df = pd.DataFrame(self.trades)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]
        
        return {
            'Total Trades': len(df),
            'Win Rate (%)': round(len(wins) / len(df) * 100, 2),
            'Total Profit ($)': round(df['pnl'].sum(), 2),
            'Avg Win ($)': round(wins['pnl'].mean(), 2) if len(wins) > 0 else 0,
            'Avg Loss ($)': round(abs(losses['pnl'].mean()), 2) if len(losses) > 0 else 0,
            'Profit Factor': round(wins['pnl'].sum() / abs(losses['pnl'].sum()), 2) if losses['pnl'].sum() != 0 else 0
        }

def main():
    """Main execution"""
    print("="*60)
    print("ICT/SMC TRADING SYSTEM")
    print("="*60)
    
    # Download data
    print("\n📥 Downloading data...")
    data = yf.download('EURUSD=X', period='3mo', interval='5m', progress=False)
    data = data.reset_index()
    data.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    print(f"✅ Downloaded {len(data)} candles")
    
    # Run strategy
    print("\n🔧 Analyzing...")
    strategy = ICTTradingSystem(data)
    signals = strategy.generate_signals()
    
    # Show signals
    print("\n" + "="*60)
    print("📊 LATEST SIGNALS")
    print("="*60)
    
    for _, row in signals.tail(10).iterrows():
        if row['action'] != 'HOLD':
            print(f"\n⏰ {row['timestamp']}")
            print(f"   🎯 {row['action']} @ ${row['price']:.5f}")
            print(f"   💪 Confidence: {row['confidence']:.0f}%")
            print(f"   📝 {row['reasons']}")
    
    # Backtest
    print("\n" + "="*60)
    print("📈 BACKTEST RESULTS")
    print("="*60)
    
    backtester = Backtester(strategy)
    trades = backtester.run()
    results = backtester.results()
    
    for key, value in results.items():
        print(f"   {key}: {value}")
    
    # Plot
    print("\n📊 Generating chart...")
    strategy.plot(days=7)
    
    print("\n✅ Complete!")

if __name__ == "__main__":
    main()