[out:json][timeout:{{overpass_timeout_seconds}}];
(
  way["building"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  relation["building"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
);
out body;
>;
out skel qt;
