[out:json][timeout:{{overpass_timeout_seconds}}];
(
  node["place"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  way["place"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  relation["place"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
);
out body;
>;
out skel qt;

