package session

import "testing"

func TestPhaseOneSessionStateTransitionsRemainNarrow(t *testing.T) {
	cases := []struct {
		from State
		to   State
		want bool
	}{
		{StateRequested, StatePendingWorker, true},
		{StateRequested, StateFailed, true},
		{StateRequested, StateCancelled, true},
		{StatePendingWorker, StateFailed, true},
		{StatePendingWorker, StateCancelled, true},
		{StatePendingWorker, StateRequested, false},
		{StateFailed, StatePendingWorker, false},
		{StateCancelled, StatePendingWorker, false},
	}
	for _, testCase := range cases {
		t.Run(string(testCase.from)+"_to_"+string(testCase.to), func(t *testing.T) {
			if got := testCase.from.CanTransitionTo(testCase.to); got != testCase.want {
				t.Fatalf("CanTransitionTo(%s -> %s) = %t, want %t", testCase.from, testCase.to, got, testCase.want)
			}
		})
	}
}
