#!/usr/bin/env python3
"""Data types for graphing and force-directed graphs."""

# This software is published under the GNU General Public License v3.0.

from typing import List, Optional


class DataSet:
    """Data set containing a list of data points for graphing."""

    def __init__(
        self, name: str, color: Optional[tuple] = None, style: List[str] = None
    ):
        """Initialize a data set.

        Args:
            name: Name of the data set
            color: Optional color tuple (BGR)
            style: List of style strings (default: ['line'])
        """
        if style is None:
            style = ["line"]
        self.name = name
        self.data_points = []
        self.color = color
        self.style = style

    def add(self, point: "DataPoint"):
        """Add a data point to the set."""
        self.data_points.append(point)

    def clear(self):
        """Clear all data points."""
        self.data_points = []


class DataPoint:
    """A single data point for graphing."""

    def __init__(
        self,
        x: float,
        y: float,
        color: Optional[tuple] = None,
        label: Optional[str] = None,
        style: List[str] = None,
        x_name: Optional[str] = None,
        y_name: Optional[str] = None,
    ):
        """Initialize a data point.

        Args:
            x: X coordinate
            y: Y coordinate
            color: Optional color tuple
            label: Optional label text
            style: List of style strings (default: ['dot'])
            x_name: Optional name for x value
            y_name: Optional name for y value
        """
        if style is None:
            style = ["dot"]
        self.x = x
        self.y = y
        self.color = color
        self.label = label
        self.style = style
        self.x_name = x_name
        self.y_name = y_name


class FdObject:
    """Object to be placed in an image for force-directed graphs."""

    def __init__(self):
        """Initialize a force-directed graph object."""
        self.name = None
        self.type = None
        self.width = None
        self.height = None
        self.initial_x = None
        self.initial_y = None
        self.fixed = False
        self.current_x = self.initial_x
        self.current_y = self.initial_y
        self.target_x = self.initial_x
        self.target_y = self.initial_y


class FdEdge:
    """Link between two objects for force-directed graphs."""

    def __init__(self):
        """Initialize a force-directed graph edge."""
        self.name = None
        self.object_a = None  # Handle to object at one end
        self.object_b = None  # Handle to object at the other end
