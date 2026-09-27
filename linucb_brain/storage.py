import json
import os
import tempfile
import numpy as np
from datetime import datetime
from typing import Dict, Any
from .models.student import Student
from .models.content import Content
from .models.session import Session

class BrainEncoder(json.JSONEncoder):
    """Custom JSON encoder for Brain objects."""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

def _atomic_write(filepath: str, payload: str):
    """
    Crash-safe file write: serialize fully in memory first, write to a temp
    file in the same directory, fsync, then atomically rename over the target.
    The previous good state is retained at <filepath>.bak via a cheap metadata
    rename, so a corrupt/failed main file can always be rolled back
    (2026-09-27).
    """
    directory = os.path.dirname(os.path.abspath(filepath))

    fd, tmp_path = tempfile.mkstemp(
        prefix=os.path.basename(filepath) + '.',
        suffix='.tmp',
        dir=directory,
    )
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(filepath):
            os.replace(filepath, filepath + '.bak')
        os.replace(tmp_path, filepath)
        dir_fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

def save_brain(brain, filepath: str):
    """
    Serialize brain state to JSON.
    """
    state = {
        'students': {id: s.__dict__ for id, s in brain.students.items()},
        'contents': {id: c.__dict__ for id, c in brain.contents.items()},
        'sessions': [s.__dict__ for s in brain.sessions],
        'model_type': brain.model_type,
        'alpha': brain.alpha,
        'gamma': getattr(brain, 'gamma', 1.0),
        'update_count': brain.update_count,
        'auto_diagnose_every': brain.auto_diagnose_every
    }
    
    if brain.model_type == "disjoint":
        state['linucb_arms'] = {
            id: {
                'A': arm['A'].tolist(),
                'A_inv': arm['A_inv'].tolist(),
                'b': arm['b'].tolist()
            } for id, arm in brain.model.arms.items()
        }
    elif brain.model_type == "hybrid":
        state['A0'] = brain.model.A0.tolist()
        state['A0_inv'] = brain.model.A0_inv.tolist()
        state['b0'] = brain.model.b0.tolist()
        state['linucb_arms'] = {
            id: {
                'A': arm['A'].tolist(),
                'A_inv': arm['A_inv'].tolist(),
                'B': arm['B'].tolist(),
                'b': arm['b'].tolist()
            } for id, arm in brain.model.arms.items()
        }
    
    payload = json.dumps(state, cls=BrainEncoder, indent=4)
    _atomic_write(filepath, payload)

def load_brain(filepath: str, brain_cls):
    """
    Reconstruct Brain object from JSON.
    Falls back to <filepath>.bak when the main state file is corrupt.
    """
    def _read(path):
        with open(path, 'r') as f:
            return json.load(f)

    try:
        state = _read(filepath)
    except (json.JSONDecodeError, ValueError):
        bak = filepath + '.bak'
        if os.path.exists(bak):
            state = _read(bak)
        else:
            raise
        
    brain = brain_cls(
        alpha=state['alpha'], 
        auto_diagnose_every=state['auto_diagnose_every'], 
        model_type=state.get('model_type', 'disjoint'),
        gamma=state.get('gamma', 1.0)
    )
    brain.update_count = state['update_count']
    
    # Reconstruct Students
    for id, s_data in state['students'].items():
        brain.students[id] = Student(**s_data)
        
    # Reconstruct Content
    for id, c_data in state['contents'].items():
        brain.contents[id] = Content(**c_data)
        
    # Reconstruct Sessions
    for s_data in state['sessions']:
        s_data['timestamp'] = datetime.fromisoformat(s_data['timestamp'])
        brain.sessions.append(Session(**s_data))
        
    # Reconstruct Model Matrices
    if brain.model_type == "disjoint":
        for id, arm_data in state['linucb_arms'].items():
            brain.model.arms[id] = {
                'A': np.array(arm_data['A']),
                'A_inv': np.array(arm_data['A_inv']),
                'b': np.array(arm_data['b'])
            }
    elif brain.model_type == "hybrid":
        brain.model.A0 = np.array(state['A0'])
        brain.model.A0_inv = np.array(state['A0_inv'])
        brain.model.b0 = np.array(state['b0'])
        for id, arm_data in state['linucb_arms'].items():
            brain.model.arms[id] = {
                'A': np.array(arm_data['A']),
                'A_inv': np.array(arm_data['A_inv']),
                'B': np.array(arm_data['B']),
                'b': np.array(arm_data['b'])
            }
        
    return brain
