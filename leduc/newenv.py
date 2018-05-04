from __future__ import print_function
import logging
import deck
import numpy as np
import ConfigParser


class Env:
    """
    Leduc Hold'em environment.
    TODO: Class description
    """

    def __init__(self):

        # Init config
        self.config = ConfigParser.ConfigParser()
        self.config.read("./config.ini")

        # Init config variables
        self.player_count = int(self.config.get('Environment', 'Playercount'))
        self.decksize = int(self.config.get('Environment', 'Decksize'))
        self.max_rounds = int(self.config.get('Environment', 'MaxRounds'))
        self.suits = int(self.config.get('Environment', 'Suits'))
        self.max_raises = int(self.config.get('Environment', 'MaxRaises'))
        self._action_space = int(self.config.get('Environment', 'ActionSpace'))
        self.total_action_space = int(self.config.get('Environment', 'TotalActionSpace'))

        # Init deck
        self.deck = deck.Deck(self.decksize)

        # Init cards vector
        self.cards = []

        # Init game variables
        self.specific_cards = np.zeros((self.player_count, self.max_rounds, (self.decksize / self.suits)))
        self.round = 0
        self.terminated = False
        self.raises = []
        self.calls = []
        self.public_card_index = 0
        self.p_card_revealed = False
        self.overall_raises = []
        self.reward = []
        self.round_raises = 0
        self.last_action = []

        self.actions_done = []

        # Init specific state
        self.history = np.zeros((self.player_count, self.max_rounds, self.max_raises, self._action_space))

    @property
    def round_index(self):
        return self.round

    @property
    def action_space(self):
        a = np.zeros(self.total_action_space)
        return a.shape

    @property
    def observation_space(self):
        o = self.history.flatten()
        c = self.specific_cards[0].flatten()
        s = np.concatenate((o, c), axis=0)
        s = np.zeros((1, len(s)))
        print("FINAL S: {}".format(s.shape))
        return s.shape

    def reset(self):
        # Re-init deck as Object of type deck
        self.deck = deck.Deck(self.decksize)
        self.deck.shuffle()

        # Reset history to empty
        self.history = np.zeros((self.player_count, self.max_rounds, self.max_raises, self._action_space))

        self.round = 0
        self.terminated = False
        self.raises = np.zeros(self.player_count)
        self.calls = np.zeros(self.player_count)
        self.overall_raises = np.zeros(self.player_count)
        self.p_card_revealed = False
        self.public_card_index = 0
        self.reward = np.zeros(self.player_count)
        self.round_raises = 0
        self.last_action = np.zeros((self.player_count, self.total_action_space))

        self.actions_done = []

        # Init specific cards
        self.specific_cards = np.zeros((self.player_count, self.max_rounds, (self.decksize / self.suits)))

        # Init players specific state
        for k in range(self.player_count):
            card_index = self.deck.pick_up().rank
            # Because 6 cards with 3 duplicates we just need 3 entrys in cards vector
            # Each possible rank is represented by one vector object
            # Set cards vector entry to 1 where the picked up card matches
            self.specific_cards[k][self.round][card_index] = 1
            # self.specific_cards[k][1][card_index] = 1

    def get_state(self, p_index):
        cards = self.specific_cards[p_index]
        state = np.concatenate((self.history.flatten(), self.specific_cards[p_index].flatten()))
        # TODO make it dynamic
        state = np.reshape(state, (1, 1, 30))
        action = np.reshape(self.last_action[p_index], (1, 1, 3))
        if self.terminated:
            return state, action, self.reward[p_index], self.terminated
        else:
            # Return zero as reward because there is no
            return state, action, 0, self.terminated

    def step(self, action, p_index):
        """

        :param action:
        :param p_index:
        :return:
        """

        # Deconstruct raises, calls, round etc
        o_index = 1 if p_index == 0 else 1  # TODO: make it dynamic for more than 2 players!
        p_calls = self.calls[p_index]
        o_calls = self.calls[o_index]
        p_raises = self.raises[p_index]
        o_raises = self.raises[o_index]

        # Get action with highest value
        action_value = np.argmax(action)
        self.last_action[p_index] = action

        # If player has raised in this round before - action_value is set to
        # call - 0 to 2 raises are allowed. Maximum one raise per player.
        if p_raises == 1 and action_value == 2:
            action_value = 1

        # For setting action to history because folding is not encoded
        action_index = action_value - 1

        # Execute actions:
        # Fold:
        if action_value == 0:
            self.terminated = True
            self.actions_done.append('Fold')

        # Check, call
        elif action_value == 1:
            self.history[p_index][self.round][self.round_raises][action_index] = 1
            p_calls += 1
            self.round_raises += 1
            self.calls[p_index] += 1
            self.actions_done.append('Call')

        # Raise
        elif action_value == 2:
            self.history[p_index][self.round][self.round_raises][action_index] = 1
            p_raises += 1
            self.raises[p_index] += 1
            self.overall_raises[p_index] += 1
            self.round_raises += 1
            self.actions_done.append('Raise')

        # Check if game or round has terminated and not folded
        round_over = False
        if not self.terminated and len(self.actions_done) == 2:
            if self.actions_done[0] == 'Call' and self.actions_done[1] == 'Call' \
                    or self.actions_done[0] == 'Raise' and self.actions_done[1] == 'Call':
                round_over = True
        elif not self.terminated and len(self.actions_done) == 3:
            if self.actions_done[0] == 'Call' and self.actions_done[1] == 'Raise' and self.actions_done[2] == 'Call' \
                    or self.actions_done[0] == 'Raise' and self.actions_done[1] == 'Raise' and self.actions_done[2] == 'Call':
                round_over = True

        if round_over:
            if self.round == 1:
                # Game has terminated
                self.terminated = True
            elif self.round == 0:
                # Update card vector of next round with private card from round_k-1
                self.specific_cards[p_index][(self.round + 1)] = self.specific_cards[p_index][self.round]
                self.specific_cards[o_index][(self.round + 1)] = self.specific_cards[o_index][self.round]

                # Update card vector for next round with revealed public card
                self.public_card_index = self.deck.pick_up().rank
                self.specific_cards[p_index][(self.round + 1)][self.public_card_index] = 1
                self.specific_cards[o_index][(self.round + 1)][self.public_card_index] = 1

                self.p_card_revealed = True
                # Determine reward from first round
                self.reward[p_index] = np.sum(self.overall_raises)
                self.reward[o_index] = np.sum(self.overall_raises)
                self.round = 1
                # Set raises and calls to zero - in new round nothing happened
                # so far
                self.raises = np.zeros(2)
                self.calls = np.zeros(2)
                self.round_raises = 0
                # Print actions done in round:
                # print("Player{} has finised".format(p_index))
                print("Actions done: {}".format(self.actions_done))
                self.actions_done = []
            else:
                print("Round not specified.")

        # Determine rewards if terminated
        if self.terminated:
            print("Terminated, actions: {}".format(self.actions_done))
            # Player has folded: Reward is at least zero
            if action_value == 0:
                if self.round == 0:
                    if p_raises > 0:
                        self.reward[p_index] = p_raises * (-1)
                        self.reward[o_index] = p_raises
                    else:
                        self.reward[p_index] = 0
                        self.reward[o_index] = 0
                else:
                    if p_raises > 0:
                        self.reward[p_index] += p_raises
                        self.reward[p_index] *= -1
                        self.reward[o_index] += p_raises
                    else:
                        self.reward[p_index] = self.reward[o_index] * (-1)

                if abs(self.reward[p_index]) - abs(self.reward[o_index]) != 0:
                    print("p-index: {}, o_index: {}".format(self.reward[p_index], self.reward[o_index]))

            # No one has folded, check winner by card
            else:
                # Deconstruct cards
                p_cards = self.specific_cards[p_index][self.round]
                o_cards = self.specific_cards[o_index][self.round]

                # Compute total reward
                self.reward[p_index] = np.sum(self.overall_raises)
                self.reward[o_index] = self.reward[p_index]
                if abs(self.reward[p_index]) - abs(self.reward[o_index]) != 0:
                    print("p_index: {}, o_index: {}".format(self.reward[p_index], self.reward[o_index]))

                # Check if one player has same card as public card
                # If just one index has value 1, the player has same rank
                # as public card.
                if np.count_nonzero(p_cards) == 1:
                    # Player wins
                    self.reward[o_index] *= -1
                elif np.count_nonzero(o_cards) == 1:
                    # Opponent wins
                    self.reward[p_index] *= -1
                else:
                    # No player has match with public card, remove public card
                    p_cards[self.public_card_index] = 0
                    o_cards[self.public_card_index] = 0
                    if np.argmax(p_cards) < np.argmax(o_cards):
                        # Player wins
                        self.reward[o_index] *= -1
                    elif np.argmax(p_cards) > np.argmax(o_cards):
                        # Opponent wins
                        self.reward[p_index] *= -1
                    elif np.argmax(p_cards) == np.argmax(o_cards):
                        # Draw
                        self.reward = np.zeros(2)
