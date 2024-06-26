import gym
import time
import numpy as np
import tensorflow as tf
import ddpg
import os


TRAIN_MODE = True


try:  
    os.mkdir('./saved')
except OSError:  
    print ("Creation of the directory failed")
else:  
    print ("Successfully created the directory")

print(tf.__version__)
print(gym.__version__)
#env = gym.make('Pendulum-v1', render_mode="human")
env = gym.make('Pendulum-v1')

critic = ddpg.Critic()
actor = ddpg.Actor()
target_critic = ddpg.TargetCritic()
target_actor = ddpg.TargetActor()

try:
    critic.load()
    actor.load()
except Exception as e:
    print(e.__repr__)

target_actor.hard_copy(actor.model.trainable_variables)
target_critic.hard_copy(critic.model.trainable_variables)

ou = ddpg.OrnsteinUhlenbeckActionNoise(mu=np.zeros(1,))
buffer = ddpg.ReplayBuffer(100000)
global ep_ave_max_q_value
ep_ave_max_q_value = 0
global total_reward
total_reward = 0

def create_tensorboard():
    global_step = tf.compat.v1.train.get_or_create_global_step()

    logdir = "./logs/"
    writer = tf.summary.create_file_writer(logdir)
    writer.set_as_default()
    return global_step, writer

global global_step
global_step, writer = create_tensorboard()

def train(action, reward, state, state2, done):
    global ep_ave_max_q_value
    
    buffer.add(state, action, reward, done, state2)
    batch_size = 64

    if buffer.size() > batch_size:
        s_batch, a_batch, r_batch, t_batch, s2_batch = buffer.sample_batch(batch_size)

        target_action2 = target_actor.model.predict(s2_batch)
        predicted_q_value = target_critic.model.predict([s2_batch, target_action2])

        yi = []
        for i in range(batch_size):
            if t_batch[i]:
                yi.append(r_batch[i])
            else:
                yi.append(r_batch[i] + 0.99 * predicted_q_value[i])

        predictions = critic.train_step(s_batch, a_batch, yi)

        ep_ave_max_q_value += np.amax(predictions)

        grad = critic.actor_gradient(s_batch, actor)
        actor.train_step(s_batch, grad)

        target_actor.update(actor.model.trainable_variables)
        target_critic.update(critic.model.trainable_variables)



EPISODES = 20000

for episode in range(EPISODES):
    global_step.assign_add(1)

    obs = env.reset()
    obs = np.array(obs[0])
    done = False
    j = 0
    ep_ave_max_q_value = 0
    total_reward = 0
    while (not done):
        if not TRAIN_MODE:
            env.render()

        obs = obs.reshape((1, 3))
        
        noise = ou()
        action = actor.model.predict(obs)

        if TRAIN_MODE:
            action = action + noise

        obs2, reward, terminated, truncated,  info = env.step(action)
        total_reward += reward

        done = terminated or truncated

        if TRAIN_MODE:
            train(action, reward, obs, obs2.reshape((1, 3)), done)
        obs = obs2
        j += 1

    with writer.as_default(), tf.summary.record_if(True):
        tf.summary.scalar("average_max_q", ep_ave_max_q_value / float(j), step=1)
        tf.summary.scalar("reward", total_reward, step=2)


    if TRAIN_MODE:
        critic.save()
        actor.save()
        
        for i in range(10): print('~~~')
        print('average_max_q: ', ep_ave_max_q_value / float(j), 'reward: ', total_reward, 'episode:', episode)
        for i in range(10): print('~~~')

env.close()

#reward = -(theta2 + 0.1 * theta_dt2 + 0.001 * torque2)
