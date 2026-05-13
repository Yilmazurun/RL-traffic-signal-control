import torch
import torch.nn as nn
import torch.optim as optim
import random
import numpy as np
import os
from collections import deque

# 1. YAPAY SİNİR AĞI (Beyin)
class DQLNetwork(nn.Module):
    def __init__(self, input_size, output_size):
        super(DQLNetwork, self).__init__()
        self.fc1 = nn.Linear(input_size, 64)
        self.fc2 = nn.Linear(64, 64)
        self.fc3 = nn.Linear(64, output_size)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        return self.fc3(x)

# 2. DENEYİM HAFIZASI (Replay Buffer)
class ReplayBuffer:
    def __init__(self, max_size=10000):
        self.buffer = deque(maxlen=max_size)
    
    def add(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))
    
    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        return states, actions, rewards, next_states, dones
    
    def size(self):
        return len(self.buffer)

# 3. KAVŞAK AJANI (Karar Verici)
class DQNAgent:
    def __init__(self, input_size, output_size):
        self.input_size = input_size 
        self.output_size = output_size 
        
        self.gamma = 0.95        
        self.epsilon = 1.0       
        self.epsilon_min = 0.01  
        self.epsilon_decay = 0.995 
        self.learning_rate = 0.001
        self.batch_size = 32
        
        self.model = DQLNetwork(input_size, output_size)
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        self.criterion = nn.MSELoss() 
        
        self.memory = ReplayBuffer()

    def act(self, state):
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.output_size) 
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            q_values = self.model(state_tensor)
        return torch.argmax(q_values[0]).item() 

    def replay(self):
        if self.memory.size() < self.batch_size:
            return
        
        states, actions, rewards, next_states, dones = self.memory.sample(self.batch_size)
        
        states = torch.FloatTensor(np.array(states))
        actions = torch.LongTensor(actions).unsqueeze(1)
        rewards = torch.FloatTensor(rewards).unsqueeze(1)
        next_states = torch.FloatTensor(np.array(next_states))
        dones = torch.FloatTensor(dones).unsqueeze(1)
        
        current_q_values = self.model(states).gather(1, actions)
        
        next_q_values = self.model(next_states).max(1)[0].unsqueeze(1)
        target_q_values = rewards + (self.gamma * next_q_values * (1 - dones))
        
        loss = self.criterion(current_q_values, target_q_values)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    def update_epsilon(self):
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def save_model(self, model_adi):
        torch.save(self.model.state_dict(), f"{model_adi}.pth")

    def load_model(self, model_adi):
        if os.path.exists(f"{model_adi}.pth"):
            self.model.load_state_dict(torch.load(f"{model_adi}.pth"))
            self.epsilon = 0.20 
            print(f">>> [{model_adi}] Hafızası başarıyla yüklendi! Kaldığı yerden devam ediyor.")